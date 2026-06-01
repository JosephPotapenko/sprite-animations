from __future__ import annotations

from PIL import Image, ImageDraw

from app.engine.animation import SpriteAnimator
from app.engine.prompt import PromptSettings


def make_base_sprite() -> Image.Image:
    image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((84, 48, 172, 136), fill=(255, 210, 160, 255))
    draw.rectangle((104, 136, 152, 212), fill=(80, 120, 240, 255))
    draw.rectangle((84, 140, 104, 208), fill=(70, 100, 210, 255))
    draw.rectangle((152, 140, 172, 208), fill=(70, 100, 210, 255))
    return image


def test_all_builtin_animations_produce_256_square_frames():
    base = make_base_sprite()
    animation_names = ['idle', 'walk', 'run', 'jump', 'attack', 'ranged', 'cast', 'hurt', 'damage', 'heal', 'buff', 'shield', 'poison', 'spin', 'bounce', 'custom']

    for animation in animation_names:
        settings = PromptSettings(animation=animation, frames=6, fps=10, intensity=1.0, direction='right')
        frames = SpriteAnimator(base, settings, seed=7).generate()

        assert len(frames) == 6
        assert all(frame.size == (256, 256) for frame in frames)
