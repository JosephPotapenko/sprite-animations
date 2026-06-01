from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageChops

from .image_ops import CANVAS_SIZE, affine, ensure_canvas
from .prompt import PromptSettings


class SpriteAnimator:
    def __init__(self, base: Image.Image, settings: PromptSettings, seed: int | None = None):
        base_image = ensure_canvas(base, CANVAS_SIZE)
        self.base = ImageOps.mirror(base_image) if settings.direction == 'left' else base_image
        self.s = settings
        self.rng = random.Random(seed)
        self.size = self.base.size[0]

    def generate(self) -> list[Image.Image]:
        fn = getattr(self, f'_anim_{self.s.animation}', self._anim_walk)
        return [ensure_canvas(frame, self.size) for frame in fn()]

    def _phase(self, index: int) -> float:
        return (index / max(1, self.s.frames)) * math.tau

    def _t(self, index: int) -> float:
        return index / max(1, self.s.frames - 1)

    def _amp(self, value: float) -> float:
        return value * self.s.intensity

    def _move_x(self, amount: float) -> float:
        return -amount if self.s.direction == 'left' else amount

    def _compose(self, body: Image.Image, effects: list[Image.Image] | None = None) -> Image.Image:
        out = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
        out.alpha_composite(body)
        if effects:
            for effect in effects:
                out.alpha_composite(effect)
        return out

    def _overlay(self, color: tuple[int, int, int], alpha: int) -> Image.Image:
        return Image.new('RGBA', self.base.size, color + (max(0, min(255, alpha)),))

    def _overlay_masked(self, body: Image.Image, color: tuple[int, int, int], alpha: int, glow: int = 6) -> Image.Image:
        """Create a subtle, transparent colored overlay confined to the sprite's alpha.

        This overlay is intended to sit on top of the sprite (no external outline
        or backdrop). The `glow` parameter is ignored to avoid creating an outline.
        """
        size = self.base.size
        mask = body.split()[3]
        if mask.getbbox() is None:
            return Image.new('RGBA', size, (0, 0, 0, 0))

        alpha = max(0, min(255, alpha))
        solid = Image.new('RGBA', size, color + (alpha,))
        mask_alpha = mask.point(lambda p: int(p * (alpha / 255)))
        overlay = Image.new('RGBA', size, (0, 0, 0, 0))
        overlay.paste(solid, (0, 0), mask_alpha)
        return overlay

    def _outline_masked(self, body: Image.Image, color: tuple[int, int, int], opacity: int = 60, radius: int = 2) -> Image.Image:
        """Create a subtle colored outline around the sprite using the alpha channel.

        - `opacity` is the maximum alpha of the outline (0-255).
        - `radius` controls how thick the outline is (small integer).
        """
        size = self.base.size
        alpha = body.split()[3]
        if alpha.getbbox() is None:
            return Image.new('RGBA', size, (0, 0, 0, 0))

        # Grow the alpha to create an outline region, then subtract the original alpha
        grown = alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))
        rim = ImageChops.subtract(grown, alpha)
        if rim.getbbox() is None:
            return Image.new('RGBA', size, (0, 0, 0, 0))

        # Scale rim intensity by requested opacity
        rim = rim.point(lambda v: int(v * (opacity / 255)))
        outline = Image.new('RGBA', size, color + (0,))
        outline.putalpha(rim)
        # Slight blur to soften the rim a bit
        outline = outline.filter(ImageFilter.GaussianBlur(radius=1))
        return outline

    # ring effects removed to keep overlays subtle and sprite-localized

    def _aura(self, t: float, center: tuple[int, int] = (128, 118), radius: int = 30, color: tuple[int, int, int, int] = (120, 180, 255, 120)) -> Image.Image:
        # Aura no longer draws a central filled sphere. Return transparent image.
        # Use `_outline_masked(body, ...)` from animation methods to produce
        # sprite-following outlines instead.
        return Image.new('RGBA', self.base.size, (0, 0, 0, 0))

    def _anim_idle(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            breath = math.sin(p)
            sway = math.sin(p * 0.5)
            frames.append(
                affine(
                    self.base,
                    1 + 0.016 * breath,
                    1 - 0.02 * breath,
                    shear=0.014 * sway,
                    angle=0.7 * sway,
                    translate=(self._move_x(1.2 * sway), self._amp(2.4 * breath)),
                )
            )
        return frames

    def _anim_walk(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            stride = math.sin(p)
            step = abs(stride)
            frames.append(
                affine(
                    self.base,
                    1.0 + 0.006 * step,
                    1.0 - 0.01 * step,
                    shear=0.006 * stride,
                    angle=-0.6 * stride,
                    translate=(self._move_x(self._amp(2.0 * stride)), self._amp(-1.0 * step)),
                )
            )
        return frames

    def _anim_run(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            stride = math.sin(p)
            lift = abs(math.sin(p))
            frames.append(
                affine(
                    self.base,
                    1.02 + 0.006 * lift,
                    0.98 - 0.006 * lift,
                    shear=0.01 * stride,
                    angle=-1.0 * stride,
                    translate=(self._move_x(self._amp(3.0 * stride)), self._amp(-1.8 * lift - 0.5)),
                )
            )
        return frames

    def _anim_jump(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            arc = math.sin(math.pi * t)
            if t < 0.26:
                takeoff = t / 0.26
                ease = takeoff * takeoff * (3 - 2 * takeoff)
                scale_x = 1.02 - 0.02 * ease
                scale_y = 0.94 + 0.04 * ease
                y = self._amp(2 * ease)
            elif t < 0.84:
                scale_x = 1.01 + 0.008 * arc
                scale_y = 0.95 - 0.02 * arc
                y = self._amp(-18 * arc)
            else:
                land = (t - 0.84) / 0.16
                ease = land * land * (3 - 2 * land)
                scale_x = 1.01 + 0.02 * ease
                scale_y = 0.96 - 0.03 * ease
                y = self._amp(-3 * (1 - ease))
            frames.append(affine(self.base, scale_x, scale_y, translate=(0, y)))
        return frames

    def _anim_attack(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            windup = min(1.0, t / 0.4)
            strike = max(0.0, min(1.0, (t - 0.38) / 0.22))
            recover = max(0.0, min(1.0, (t - 0.6) / 0.4))
            ease_wind = windup * windup * (3 - 2 * windup)
            ease_strike = strike * strike * (3 - 2 * strike)
            ease_recover = recover * recover * (3 - 2 * recover)
            body = affine(
                self.base,
                1.0 + 0.01 * ease_strike,
                1.0 - 0.01 * ease_strike,
                shear=0.005 * ease_wind + 0.02 * ease_strike,
                angle=self._amp(-2 * ease_wind + 4 * ease_strike - 0.6 * ease_recover),
                translate=(self._move_x(self._amp(-3 * ease_wind + 8 * ease_strike - 1.5 * ease_recover)), self._amp(0.6 * ease_wind - 1.0 * ease_strike + 0.4 * ease_recover)),
            )
            frames.append(body)
        return frames

    def _anim_ranged(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            pull = min(1.0, t / 0.4)
            aim = max(0.0, min(1.0, (t - 0.32) / 0.28))
            release = max(0.0, min(1.0, (t - 0.6) / 0.4))
            ease_pull = pull * pull * (3 - 2 * pull)
            ease_aim = aim * aim * (3 - 2 * aim)
            ease_release = release * release * (3 - 2 * release)
            body = affine(
                self.base,
                1.0 + 0.008 * ease_aim,
                1.0 - 0.008 * ease_aim,
                shear=0.008 * ease_pull,
                angle=self._amp(-3 * ease_pull + 1 * ease_aim + 4 * ease_release),
                translate=(self._move_x(self._amp(-4 * ease_pull + 1 * ease_aim + 8 * ease_release)), self._amp(0.5 * ease_pull - 0.8 * ease_aim - 0.9 * ease_release)),
            )
            trail = None
            if t > 0.55:
                trail = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(trail, 'RGBA')
                alpha = int(80 * ease_release)
                x0 = 146 if self.s.direction != 'left' else 110
                x1 = x0 + (28 if self.s.direction != 'left' else -28)
                y = 124 - int(6 * ease_release)
                draw.line((x0, y, x1, y - 3), fill=(255, 255, 255, alpha), width=2)
                draw.line((x0, y + 4, x1, y), fill=(120, 210, 255, alpha // 2), width=1)
            frames.append(self._compose(body, [trail] if trail else None))
        return frames

    def _anim_cast(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            pulse = abs(math.sin(p))
            body = affine(
                self.base,
                1.0 + 0.006 * pulse,
                1.0 - 0.008 * pulse,
                angle=0.25 * math.sin(p * 0.5),
                translate=(self._move_x(0.4 * math.sin(p * 0.5)), self._amp(-1.0 * pulse)),
            )
            # replace central aura with sprite-following outline
            outline = self._outline_masked(body, (150, 120, 255), opacity=int(38 * pulse), radius=1)
            frames.append(self._compose(body, [outline]))
        return frames

    def _anim_hurt(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            kick = max(0.0, 1 - t)
            body = affine(
                self.base,
                1.0,
                1.0,
                angle=self._amp((-1 if i % 2 else 1) * kick * 0.3),
                translate=(self._move_x(self._amp(-6 * kick)), self._amp(-0.8 * math.sin(kick * math.pi))),
            )
            effects = []
            if kick > 0.05:
                effects.append(self._overlay_masked(body, (255, 40, 30), int(14 * kick), glow=0))
                effects.append(self._outline_masked(body, (200, 40, 30), opacity=int(28 * kick), radius=1))
            frames.append(self._compose(body, effects))
        return frames

    def _anim_damage(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            recoil = max(0.0, 1 - t)
            # Make the jolt/wiggle very subtle: reduce amplitude and translation
            jolt = 0.45 * math.sin(t * math.tau * 2)
            body = affine(
                self.base,
                1.0 - 0.02 * recoil,
                1.0 + 0.008 * recoil,
                shear=0.006 * recoil,
                angle=self._amp((-1 if i % 2 else 1) * (2.0 * recoil + 0.6 * jolt)),
                translate=(self._move_x(self._amp(-4 * recoil - 1.0 * jolt)), self._amp(-1.0 * recoil)),
            )
            effects = [self._overlay_masked(body, (255, 48, 40), int(20 * recoil), glow=0), self._outline_masked(body, (220, 80, 70), opacity=int(30 * recoil), radius=1)]
            frames.append(self._compose(body, effects))
        return frames

    def _anim_heal(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            pulse = math.sin(math.pi * t)
            body = affine(
                self.base,
                1.0 + 0.012 * pulse,
                1.0 - 0.01 * pulse,
                angle=0.4 * math.sin(self._phase(i) * 0.5),
                translate=(0, self._amp(-3 * pulse)),
            )
            effects = [self._overlay_masked(body, (255, 255, 255), int(12 * pulse), glow=0), self._outline_masked(body, (255, 240, 220), opacity=int(26 * pulse), radius=1)]
            frames.append(self._compose(body, effects))
        return frames

    def _anim_buff(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            pulse = abs(math.sin(self._phase(i)))
            body = affine(
                self.base,
                1.0 + 0.008 * pulse,
                1.0 - 0.008 * pulse,
                angle=0.5 * math.sin(self._phase(i) * 0.5),
                translate=(self._move_x(0.35 * math.sin(self._phase(i) * 0.5)), self._amp(-1.5 * pulse)),
            )
            # replace aura with sprite outline + subtle overlay
            effects = [self._overlay_masked(body, (255, 220, 130), int(8 * pulse), glow=0), self._outline_masked(body, (220, 180, 100), opacity=int(18 * pulse), radius=1)]
            frames.append(self._compose(body, effects))
        return frames

    def _anim_shield(self):
        frames = []
        for i in range(self.s.frames):
            pulse = 0.5 + 0.5 * math.sin(self._phase(i))
            body = affine(
                self.base,
                1.0 + 0.008 * pulse,
                1.0 - 0.008 * pulse,
                angle=0.35 * math.sin(self._phase(i) * 0.5),
                translate=(0, self._amp(-1.2 * pulse)),
            )
            effects = [self._outline_masked(body, (120, 180, 255), opacity=int(22 * pulse), radius=1)]
            frames.append(self._compose(body, effects))
        return frames

    def _anim_poison(self):
        frames = []
        for i in range(self.s.frames):
            phase = self._phase(i)
            flicker = 0.55 + 0.45 * math.sin(phase * 3.0 + 0.8)
            wobble_x = self._amp((self.rng.uniform(-1.0, 1.0) * 0.5) + 0.6 * math.sin(phase * 2.0))
            wobble_y = self._amp(0.5 * math.sin(phase * 2.4))
            body = affine(
                self.base,
                1.0 + 0.01 * math.sin(phase * 2.0),
                1.0 - 0.01 * math.sin(phase * 2.0),
                shear=0.015 * math.sin(phase * 2.0),
                angle=1.2 * math.sin(phase * 1.8),
                translate=(wobble_x, wobble_y),
            )
            effects = [self._overlay_masked(body, (70, 200, 90), int(12 * flicker), glow=0), self._outline_masked(body, (90, 200, 120), opacity=int(20 * flicker), radius=1)]
            frames.append(self._compose(body, effects))
        return frames

    def _anim_spin(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            phase = self._phase(i)
            frames.append(
                affine(
                    self.base,
                    1.0 - 0.04 * abs(math.sin(phase)),
                    1.0 + 0.02 * abs(math.sin(phase)),
                    shear=0.01 * math.sin(phase * 2),
                    angle=180 * t,
                    translate=(0, self._amp(-1.5 * abs(math.sin(phase)))),
                )
            )
        return frames

    def _anim_bounce(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            peak = abs(math.sin(p))
            frames.append(
                affine(
                    self.base,
                    1.0 + 0.04 * (1 - peak),
                    1.0 - 0.05 * (1 - peak),
                    translate=(0, self._amp(-18 * peak)),
                )
            )
        return frames

