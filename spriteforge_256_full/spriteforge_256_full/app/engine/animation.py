from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageOps

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

    def _trail_direction(self) -> str:
        return {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}.get(self.s.direction, 'left')

    def _compose(self, body, effects=None):
        out = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
        out.alpha_composite(body)
        if effects:
            for effect in effects:
                out.alpha_composite(effect)
        return out

    def _aura(self, t: float, center=(128, 118), radius: int = 30, color=(120, 180, 255, 120)):
        im = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(im, 'RGBA')
        pulse = 0.4 + 0.6 * abs(math.sin(t * math.tau))
        r = int(radius * pulse)
        alpha = int(color[3] * pulse)
        draw.ellipse((center[0] - r, center[1] - r, center[0] + r, center[1] + r), outline=color[:3] + (alpha,), width=3)
        draw.ellipse((center[0] - r // 2, center[1] - r // 2, center[0] + r // 2, center[1] + r // 2), outline=(255, 255, 255, max(0, alpha - 30)), width=1)
        return im

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
                    1.0 + 0.012 * step,
                    1.0 - 0.02 * step,
                    shear=0.012 * stride,
                    angle=-1.1 * stride,
                    translate=(self._move_x(self._amp(3.5 * stride)), self._amp(-2.0 * step)),
                )
            )
        return frames

    def _anim_run(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            stride = math.sin(p)
            lift = abs(math.sin(p))
            frame = affine(
                self.base,
                1.02 + 0.01 * lift,
                0.96 - 0.01 * lift,
                shear=0.02 * stride,
                angle=-2.0 * stride,
                translate=(self._move_x(self._amp(5.5 * stride)), self._amp(-3.2 * lift - 0.5)),
            )
            frames.append(frame)
        return frames

    def _anim_jump(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            arc = math.sin(math.pi * t)
            if t < 0.26:
                takeoff = t / 0.26
                ease = takeoff * takeoff * (3 - 2 * takeoff)
                scale_x = 1.04 - 0.03 * ease
                scale_y = 0.91 + 0.07 * ease
                y = self._amp(4 * ease)
            elif t < 0.84:
                rise = (t - 0.26) / 0.58
                scale_x = 1.01 + 0.015 * arc
                scale_y = 0.93 - 0.04 * arc
                y = self._amp(-40 * arc)
            else:
                land = (t - 0.84) / 0.16
                ease = land * land * (3 - 2 * land)
                scale_x = 1.01 + 0.05 * ease
                scale_y = 0.93 - 0.06 * ease
                y = self._amp(-5 * (1 - ease))
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
                1.0 + 0.02 * ease_strike,
                1.0 - 0.02 * ease_strike,
                shear=0.01 * ease_wind + 0.03 * ease_strike,
                angle=self._amp(-4 * ease_wind + 8 * ease_strike - 1.5 * ease_recover),
                translate=(self._move_x(self._amp(-4 * ease_wind + 14 * ease_strike - 3 * ease_recover)), self._amp(1.2 * ease_wind - 2.0 * ease_strike + 0.8 * ease_recover)),
            )
            frames.append(body)
        return frames

    def _slash_arc(self, t):
        im = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(im, 'RGBA')
        alpha = int(150 * (1 - abs(t - 0.46) * 2.2))
        alpha = max(0, min(170, alpha))
        draw.arc((108, 72, 230, 194), start=-62, end=52, fill=(255, 255, 255, alpha), width=5)
        draw.arc((112, 78, 226, 188), start=-56, end=46, fill=(100, 210, 255, alpha // 2), width=2)
        return im

    def _attack_flash(self, t: float, intensity: float):
        im = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(im, 'RGBA')
        alpha = int(120 * intensity)
        size = 12 + int(10 * intensity)
        x = 160 + int(20 * math.sin(t * math.tau))
        y = 126 + int(8 * math.cos(t * math.tau))
        draw.line((x - size, y, x + size, y), fill=(255, 255, 255, alpha), width=2)
        draw.line((x, y - size, x, y + size), fill=(255, 240, 200, alpha), width=2)
        return im

    def _anim_cast(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            pulse = abs(math.sin(p))
            body = affine(
                self.base,
                1.0 + 0.01 * pulse,
                1.0 - 0.015 * pulse,
                angle=0.4 * math.sin(p * 0.5),
                translate=(self._move_x(0.8 * math.sin(p * 0.5)), self._amp(-2.0 * pulse)),
            )
            frames.append(body)
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
                angle=self._amp((-1 if i % 2 else 1) * kick * 0.8),
                translate=(self._move_x(self._amp(-10 * kick)), self._amp(-1.2 * math.sin(kick * math.pi))),
            )
            if kick > 0.05:
                flash = Image.new('RGBA', body.size, (255, 40, 30, 10))
                body = Image.alpha_composite(body, flash)
            frames.append(body)
        return frames

    def _anim_spin(self):
        frames = []
        for i in range(self.s.frames):
            t = self._t(i)
            frame = affine(
                self.base,
                1.0 - 0.04 * abs(math.sin(self._phase(i))),
                1.0 + 0.02 * abs(math.sin(self._phase(i))),
                shear=0.01 * math.sin(self._phase(i) * 2),
                angle=180 * t,
                translate=(0, self._amp(-1.5 * abs(math.sin(self._phase(i))))),
            )
            frames.append(frame)
        return frames

    def _anim_bounce(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            peak = abs(math.sin(p))
            body = affine(
                self.base,
                1.0 + 0.04 * (1 - peak),
                1.0 - 0.05 * (1 - peak),
                translate=(0, self._amp(-18 * peak)),
            )
            frames.append(body)
        return frames

    def _anim_custom(self):
        frames = []
        for i in range(self.s.frames):
            p = self._phase(i)
            drift = {'right': 1, 'left': -1, 'up': 0, 'down': 0}.get(self.s.direction, 1)
            ydrift = {'up': -1, 'down': 1}.get(self.s.direction, 0)
            body = affine(
                self.base,
                1.0 + 0.01 * math.sin(p),
                1.0 - 0.01 * math.sin(p),
                shear=0.01 * math.sin(p),
                angle=0.4 * math.sin(p * 0.5),
                translate=(self._amp(2.5 * math.sin(p) * drift), self._amp(3.0 * math.sin(p) * ydrift - 1.5 * abs(math.sin(p)))),
            )
            frames.append(body)
        return frames
