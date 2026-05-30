"""
Optional AI sprite generation.

The diffusion backend stays available for larger machines, but the default
Codespaces path is a lightweight prompt-guided fallback that always returns
256x256 frames on CPU.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import math
import os
import random
import re

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ..engine.image_ops import CANVAS_SIZE, affine, ensure_canvas


class DiffusionUnavailable(RuntimeError):
    pass


def _truthy_env(name: str) -> bool:
    return os.getenv(name, '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _backend_mode() -> str:
    backend = os.getenv('SPRITEFORGE_AI_BACKEND', '').strip().lower()
    if backend:
        return backend
    if _truthy_env('CODESPACES'):
        return 'procedural'
    return 'diffusion'


def default_model_id() -> str:
    if _backend_mode() == 'procedural':
        return 'procedural-prompt-fallback'
    override = os.getenv('SPRITEFORGE_AI_MODEL_ID', '').strip()
    if override:
        return override
    return 'runwayml/stable-diffusion-v1-5'


def candidate_model_ids() -> list[str]:
    if _backend_mode() == 'procedural':
        return []
    override = os.getenv('SPRITEFORGE_AI_MODEL_ID', '').strip()
    if override:
        return [override]
    return ['runwayml/stable-diffusion-v1-5']


def is_available() -> bool:
    return True


def _resolve_device():
    import torch

    if torch.cuda.is_available():
        return 'cuda', torch.float16
    return 'cpu', torch.float32


def _prompt_key(prompt: str) -> int:
    digest = hashlib.blake2s(prompt.strip().lower().encode('utf-8'), digest_size=8).digest()
    return int.from_bytes(digest, 'big')


def _prompt_tokens(prompt: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", prompt.lower()) if token}


def _prompt_motion_mode(prompt: str) -> str:
    tokens = _prompt_tokens(prompt)
    if tokens.intersection({'bow', 'arrow', 'shoot', 'shooting', 'fire', 'firing', 'reload', 'reloading', 'quiver', 'aim'}):
        return 'ranged'
    if tokens.intersection({'slash', 'swing', 'stab', 'attack', 'punch', 'kick', 'axe', 'blade', 'strike'}):
        return 'melee'
    if tokens.intersection({'cast', 'magic', 'spell', 'summon', 'wizard', 'mage', 'channel', 'chant'}):
        return 'cast'
    if tokens.intersection({'walk', 'run', 'dash', 'jump', 'leap', 'roll', 'move', 'moving', 'travel'}):
        return 'movement'
    if tokens.intersection({'hurt', 'hit', 'damage', 'recoil', 'stagger', 'stun', 'impact'}):
        return 'impact'
    if tokens.intersection({'idle', 'wait', 'breath', 'breathing'}):
        return 'idle'
    return 'neutral'


def _prompt_style(prompt: str) -> dict[str, object]:
    text = prompt.lower()
    tokens = _prompt_tokens(prompt)
    key = _prompt_key(prompt)

    palettes = [
        {'accent': (110, 180, 255, 255), 'glow': (180, 220, 255, 50), 'contrast': 1.03, 'color': 1.04, 'sharpness': 1.02},
        {'accent': (255, 150, 90, 255), 'glow': (255, 210, 140, 60), 'contrast': 1.05, 'color': 1.08, 'sharpness': 1.05},
        {'accent': (140, 230, 170, 255), 'glow': (190, 255, 210, 60), 'contrast': 1.04, 'color': 1.1, 'sharpness': 1.04},
        {'accent': (190, 150, 255, 255), 'glow': (230, 205, 255, 55), 'contrast': 1.06, 'color': 1.0, 'sharpness': 1.03},
        {'accent': (255, 210, 120, 255), 'glow': (255, 245, 190, 50), 'contrast': 1.04, 'color': 1.06, 'sharpness': 1.04},
        {'accent': (120, 220, 240, 255), 'glow': (180, 240, 255, 55), 'contrast': 1.03, 'color': 1.05, 'sharpness': 1.03},
    ]
    palette = palettes[key % len(palettes)]

    themes = [
        ({'fire', 'flame', 'lava', 'ember', 'inferno'}, {'accent': (255, 130, 48, 255), 'glow': (255, 180, 72, 0), 'contrast': 1.08, 'color': 1.08, 'sharpness': 1.08}),
        ({'ice', 'frost', 'snow', 'glacier', 'crystal'}, {'accent': (120, 210, 255, 255), 'glow': (190, 240, 255, 0), 'contrast': 1.04, 'color': 1.05, 'sharpness': 1.04}),
        ({'poison', 'venom', 'slime', 'toxic', 'acid'}, {'accent': (120, 220, 90, 255), 'glow': (180, 255, 140, 0), 'contrast': 1.02, 'color': 1.06, 'sharpness': 1.03}),
        ({'shadow', 'dark', 'ghost', 'necromancer', 'void'}, {'accent': (145, 115, 210, 255), 'glow': (200, 170, 255, 0), 'contrast': 1.08, 'color': 0.98, 'sharpness': 1.03}),
        ({'electric', 'lightning', 'storm', 'plasma', 'arc'}, {'accent': (110, 200, 255, 255), 'glow': (245, 250, 255, 0), 'contrast': 1.06, 'color': 1.04, 'sharpness': 1.06}),
        ({'robot', 'metal', 'steel', 'mech', 'cyber'}, {'accent': (180, 200, 220, 255), 'glow': (130, 210, 255, 0), 'contrast': 1.08, 'color': 0.96, 'sharpness': 1.1}),
        ({'nature', 'forest', 'leaf', 'druid', 'earth'}, {'accent': (110, 185, 110, 255), 'glow': (180, 230, 150, 0), 'contrast': 1.03, 'color': 1.06, 'sharpness': 1.03}),
    ]
    for keywords, style in themes:
        if tokens.intersection(keywords) or any(word in text for word in keywords):
            selected = dict(palette)
            selected.update(style)
            return selected

    selected = dict(palette)
    return selected


def _apply_prompt_style(frame: Image.Image, prompt: str, frame_index: int, frame_total: int, seed: int) -> Image.Image:
    rng = random.Random(seed + frame_index * 101)
    style = _prompt_style(prompt)
    base = ensure_canvas(frame, CANVAS_SIZE).convert('RGBA')
    alpha = base.getchannel('A')
    prompt_key = _prompt_key(prompt)
    pulse = 0.85 + 0.15 * math.sin((frame_index / max(1, frame_total - 1)) * math.tau + (prompt_key % 13))

    tint = Image.new('RGBA', base.size, style['accent'])
    tint_mask = alpha.point(lambda value: int(value * (0.02 + 0.02 * pulse)))
    tint.putalpha(tint_mask)
    base = Image.alpha_composite(base, tint)

    base = ImageEnhance.Color(base).enhance(float(style['color']))
    base = ImageEnhance.Contrast(base).enhance(float(style['contrast']))
    base = ImageEnhance.Sharpness(base).enhance(float(style['sharpness']))
    base = ImageOps.autocontrast(base.convert('RGB')).convert('RGBA')

    return base


def _prompt_motion_transform(frame: Image.Image, prompt: str, frame_index: int, frame_total: int, seed: int) -> Image.Image:
    mode = _prompt_motion_mode(prompt)
    key = _prompt_key(prompt)
    phase = key / 997.0
    t = frame_index / max(1, frame_total - 1)
    swing = math.sin((t * math.tau) + phase)
    bob = math.sin((t * math.tau * 2) + phase * 0.5)
    wobble = math.cos((t * math.tau * 2) + phase)

    if mode == 'ranged':
        if t < 0.35:
            pull = t / 0.35
            return affine(frame, 1.0 + 0.03 * pull, 1.0 - 0.02 * pull, angle=-8 * pull, translate=(-8 * pull, 1 * pull))
        if t < 0.7:
            aim = (t - 0.35) / 0.35
            return affine(frame, 1.02, 0.99, angle=-2 + 2 * aim, translate=(-4 + 3 * aim, 0.5 * wobble))
        release = (t - 0.7) / 0.3
        return affine(frame, 1.0 - 0.02 * release, 1.0 + 0.01 * release, angle=6 * release, translate=(10 * release, -1 * release))

    if mode == 'melee':
        if t < 0.4:
            windup = t / 0.4
            return affine(frame, 1.0 + 0.02 * windup, 1.0 - 0.01 * windup, angle=-10 * windup, translate=(-3 * windup, 1 * windup))
        if t < 0.75:
            strike = (t - 0.4) / 0.35
            return affine(frame, 1.0 - 0.02 * strike, 1.0 + 0.01 * strike, angle=16 * strike, translate=(10 * strike, -2 * strike))
        recover = (t - 0.75) / 0.25
        return affine(frame, 1.0, 1.0, angle=4 * (1 - recover), translate=(-2 * (1 - recover), 0))

    if mode == 'cast':
        return affine(frame, 1.0 + 0.012 * bob, 1.0 - 0.01 * bob, angle=3 * swing, translate=(0, -3 * bob))

    if mode == 'movement':
        return affine(frame, 1.0 + 0.02 * abs(swing), 1.0 - 0.02 * abs(swing), shear=0.012 * swing, angle=2.0 * swing, translate=(6 * swing, -4 * abs(swing)))

    if mode == 'impact':
        kick = max(0.0, 1.0 - t)
        return affine(frame, 1.0 - 0.01 * kick, 1.0 + 0.01 * kick, angle=(-12 if frame_index % 2 else 12) * kick, translate=(-12 * kick, -2 * kick))

    if mode == 'idle':
        return affine(frame, 1.0 + 0.004 * bob, 1.0 - 0.004 * bob, translate=(0.75 * swing, 1.5 * bob))

    neutral_shift = 1.5 + 0.5 * (seed % 3)
    return affine(frame, 1.0 + 0.006 * swing, 1.0 - 0.006 * swing, shear=0.006 * swing, translate=(neutral_shift * swing, neutral_shift * bob))


def _procedural_ai_frames(base: Image.Image, prompt: str, frames: int, size: int, animation: str, seed: int | None) -> list[Image.Image]:
    frames_out: list[Image.Image] = []
    source = ensure_canvas(base, size)
    if seed is None:
        seed = 12345

    frame_total = max(2, min(32, frames))
    for frame_index in range(frame_total):
        motion_source = _motion_source(source if not frames_out else frames_out[-1], animation, frame_index, frame_total)
        prompt_motion = _prompt_motion_transform(motion_source, prompt, frame_index, frame_total, seed)
        styled = _apply_prompt_style(prompt_motion, prompt, frame_index, frame_total, seed)
        frames_out.append(ensure_canvas(styled, size))

    return frames_out


@lru_cache(maxsize=4)
def _load_pipeline(model_id: str):
    try:
        import torch
        from diffusers import StableDiffusionImg2ImgPipeline
    except Exception as exc:  # pragma: no cover - exercised through status checks
        raise DiffusionUnavailable('Install requirements-ai.txt to enable diffusion generation.') from exc

    device, dtype = _resolve_device()
    local_files_only = os.getenv('SPRITEFORGE_AI_LOCAL_ONLY', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    try:
        pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
            model_id,
            torch_dtype=dtype,
            safety_checker=None,
            requires_safety_checker=False,
            local_files_only=local_files_only,
            use_safetensors=False,
        )
    except Exception as exc:
        raise DiffusionUnavailable(
            f'Could not load the AI model "{model_id}". Check network access and whether the checkpoint exists.'
        ) from exc

    pipe = pipe.to(device)
    try:
        pipe.enable_attention_slicing()
    except Exception:
        pass
    try:
        pipe.enable_vae_slicing()
    except Exception:
        pass
    try:
        pipe.set_progress_bar_config(disable=True)
    except Exception:
        pass
    return pipe


def _run_diffusion_frames(base: Image.Image, prompt: str, frames: int, size: int, animation: str, seed: int | None) -> list[Image.Image]:
    pipe = None
    load_errors: list[str] = []
    for model_id in candidate_model_ids():
        try:
            pipe = _load_pipeline(model_id)
            break
        except DiffusionUnavailable as exc:
            load_errors.append(str(exc))
    if pipe is None:
        raise DiffusionUnavailable(' / '.join(load_errors) or 'Could not load any AI model.')

    device, _ = _resolve_device()

    try:
        import torch
    except Exception as exc:
        raise DiffusionUnavailable('PyTorch is required for AI generation.') from exc

    if seed is None:
        seed = 12345

    frames_out: list[Image.Image] = []
    source = ensure_canvas(base, size)

    for frame_index in range(max(2, min(32, frames))):
        motion_source = _motion_source(source if not frames_out else frames_out[-1], animation, frame_index, frames)
        generator = torch.Generator(device=device).manual_seed(seed + _seed_offset() * frame_index)
        prompt_text = _prompt_for(animation, prompt, frame_index, frames)
        strength = 0.28 + (0.08 if animation in {'attack', 'cast', 'spin', 'run'} else 0.04) * (0.5 + 0.5 * math.sin(frame_index / max(1, frames - 1) * math.tau))

        context = torch.inference_mode()
        if device == 'cuda':
            context = torch.autocast('cuda')

        with context:
            result = pipe(
                prompt=prompt_text,
                negative_prompt=_negative_prompt(),
                image=motion_source,
                strength=strength,
                guidance_scale=7.5,
                num_inference_steps=int(os.getenv('SPRITEFORGE_AI_STEPS', '8')),
                generator=generator,
            )

        generated = result.images[0].convert('RGBA')
        frames_out.append(ensure_canvas(generated, size))

    return frames_out


def _motion_source(base: Image.Image, animation: str, index: int, total: int) -> Image.Image:
    total = max(1, total - 1)
    t = index / total if total else 0.0
    p = t * 6.283185307179586
    frame = ensure_canvas(base, CANVAS_SIZE)

    if animation == 'idle':
        return affine(frame, 1.0 + 0.008 * __import__('math').sin(p), 1.0 - 0.01 * __import__('math').sin(p), translate=(0, 1.4 * __import__('math').sin(p)))
    if animation == 'walk':
        return affine(frame, 1.0 + 0.02 * abs(__import__('math').sin(p)), 1.0 - 0.03 * abs(__import__('math').sin(p)), shear=0.025 * __import__('math').sin(p), translate=(6 * __import__('math').sin(p), -4 * abs(__import__('math').sin(p))))
    if animation == 'run':
        return affine(frame, 1.03, 0.95, shear=0.045 * __import__('math').sin(p), translate=(11 * __import__('math').sin(p), -6 * abs(__import__('math').sin(p))))
    if animation == 'jump':
        arc = __import__('math').sin(__import__('math').pi * t)
        return affine(frame, 1.0, 1.0, translate=(0, -48 * arc))
    if animation == 'attack':
        windup = min(1.0, t / 0.35)
        strike = max(0.0, min(1.0, (t - 0.25) / 0.25))
        return affine(frame, 1.0 + 0.04 * strike, 1.0 - 0.03 * strike, shear=0.03 * windup + 0.06 * strike, angle=-10 * windup + 18 * strike, translate=(28 * strike - 8 * windup, 0))
    if animation == 'cast':
        return affine(frame, 1.0 + 0.015 * __import__('math').sin(p), 1.0 - 0.01 * __import__('math').sin(p), translate=(0, -3 * __import__('math').sin(p)))
    if animation == 'hurt':
        kick = max(0.0, 1.0 - t)
        return affine(frame, 1.0, 1.0, angle=(-12 if index % 2 else 12) * kick, translate=(-28 * kick, -4 * __import__('math').sin(kick * 3.141592653589793)))
    if animation == 'spin':
        return affine(frame, 1.0 - 0.1 * abs(__import__('math').sin(p)), 1.02 + 0.03 * abs(__import__('math').sin(p)), angle=360 * t, translate=(0, -2 * abs(__import__('math').sin(p))))
    if animation == 'bounce':
        return affine(frame, 1.0 + 0.08 * max(0.0, __import__('math').cos(p)), 1.0 - 0.08 * max(0.0, __import__('math').cos(p)), translate=(0, -20 * abs(__import__('math').sin(p))))
    return affine(frame, 1.0 + 0.02 * __import__('math').sin(p), 1.0 - 0.02 * __import__('math').sin(p), shear=0.02 * __import__('math').sin(p), translate=(5 * __import__('math').sin(p), -3 * abs(__import__('math').sin(p))))


def _prompt_for(animation: str, prompt: str, frame_index: int, frame_total: int) -> str:
    base_prompt = prompt.strip() or animation
    motion_descriptions = {
        'idle': 'subtle breathing motion, soft idle sway',
        'walk': 'walking cycle, alternating legs, slight bounce',
        'run': 'fast running cycle, dynamic motion streaks',
        'jump': 'jumping arc, airborne pose, landing anticipation',
        'attack': 'attack pose, weapon swing, impact energy',
        'cast': 'casting magic, glowing aura, hands raised',
        'hurt': 'hurt reaction, recoil, impact flash',
        'spin': 'spinning attack, circular motion blur',
        'bounce': 'bouncing motion, springy vertical movement',
        'custom': 'sprite animation frame, clean game character motion',
    }
    motion = motion_descriptions.get(animation, motion_descriptions['custom'])
    frame_note = f'frame {frame_index + 1} of {frame_total}, consistent character design, transparent background, pixel art sprite'
    return f'{base_prompt}, {motion}, {frame_note}'


@lru_cache(maxsize=1)
def _negative_prompt() -> str:
    return 'blurry, low quality, cropped, duplicated limbs, extra fingers, extra heads, background scene, watermark, text, signature'


@lru_cache(maxsize=1)
def _seed_offset() -> int:
    return 7919


def generate_ai_frames(base: Image.Image, prompt: str, frames: int = 8, size: int = 256, animation: str = 'custom', seed: int | None = None) -> list[Image.Image]:
    if not is_available():
        raise DiffusionUnavailable('AI generation is unavailable in this environment.')

    backend = _backend_mode()
    if backend == 'diffusion':
        try:
            return _run_diffusion_frames(base, prompt, frames, size, animation, seed)
        except Exception:
            return _procedural_ai_frames(base, prompt, frames, size, animation, seed)

    return _procedural_ai_frames(base, prompt, frames, size, animation, seed)
