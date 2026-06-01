from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

TRANSPARENT = (0, 0, 0, 0)
CANVAS_SIZE = 256


def _blank(size: int = CANVAS_SIZE) -> Image.Image:
    return Image.new('RGBA', (size, size), TRANSPARENT)

def open_rgba(data: bytes) -> Image.Image:
    from io import BytesIO

    return Image.open(BytesIO(data)).convert('RGBA')


def ensure_canvas(im: Image.Image, size: int = CANVAS_SIZE) -> Image.Image:
    image = im.convert('RGBA')
    if image.size == (size, size):
        return image

    canvas = _blank(size)
    resized = image
    if resized.width != size or resized.height != size:
        resized = resized.resize((size, size), Image.Resampling.NEAREST)
    canvas.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def fit_sprite(im: Image.Image, size: int = CANVAS_SIZE, padding: int = 18) -> Image.Image:
    image = im.convert('RGBA')
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    max_side = max(1, size - padding * 2)
    image.thumbnail((max_side, max_side), Image.Resampling.NEAREST)
    canvas = _blank(size)
    x = (size - image.width) // 2
    y = max(padding // 2, size - padding - image.height)
    canvas.alpha_composite(image, (x, y))
    return canvas


def remove_bg_corner(im: Image.Image, tolerance: int = 22) -> Image.Image:
    image = im.convert('RGBA')
    arr = np.array(image)
    corners = np.array([arr[0, 0, :3], arr[0, -1, :3], arr[-1, 0, :3], arr[-1, -1, :3]], dtype=np.int16)
    background = np.median(corners, axis=0)
    diff = np.linalg.norm(arr[:, :, :3].astype(np.int16) - background, axis=2)
    mask = diff < tolerance
    arr[:, :, 3] = np.where(mask, 0, arr[:, :, 3])
    return Image.fromarray(arr, 'RGBA')


def add_outline(im: Image.Image, color=(20, 20, 28, 255), radius: int = 2) -> Image.Image:
    alpha = im.split()[-1]
    grown = alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    outline = Image.new('RGBA', im.size, color)
    outline.putalpha(ImageChops.subtract(grown, alpha))
    out = _blank(im.size[0])
    out.alpha_composite(outline)
    out.alpha_composite(im)
    return out


def add_shadow(im: Image.Image, y: int = 226) -> Image.Image:
    # Create a soft shadow derived from the sprite's alpha channel.
    size = im.size[0]
    out = _blank(size)
    alpha = im.split()[-1]
    # Blur the alpha to produce a soft shadow mask
    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(radius=max(3, size // 48)))
    # Dim the shadow mask for subtlety
    shadow_mask = shadow_mask.point(lambda v: int(v * 0.28))
    shadow = Image.new('RGBA', im.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_mask)
    # Slight downward offset for the shadow
    offset_y = max(2, size // 40)
    out.alpha_composite(shadow, (0, offset_y))
    out.alpha_composite(im)
    return out


def affine(im: Image.Image, scale_x: float = 1, scale_y: float = 1, shear: float = 0, angle: float = 0, translate=(0, 0)) -> Image.Image:
    width, height = im.size
    center_x = width / 2
    center_y = height / 2
    layer = _blank(width)
    new_width = max(1, int(round(width * scale_x)))
    new_height = max(1, int(round(height * scale_y)))
    transformed = im.resize((new_width, new_height), Image.Resampling.NEAREST)
    if shear:
        transformed = transformed.transform(
            transformed.size,
            Image.Transform.AFFINE,
            (1, shear, 0, 0, 1, 0),
            resample=Image.Resampling.NEAREST,
        )
    if angle:
        transformed = transformed.rotate(angle, resample=Image.Resampling.NEAREST, expand=True)
    x = int(center_x - transformed.width / 2 + translate[0])
    y = int(center_y - transformed.height / 2 + translate[1])
    layer.alpha_composite(transformed, (x, y))
    return layer


def motion_blur_like(im: Image.Image, direction: str = 'right', amount: int = 1) -> Image.Image:
    out = _blank(im.size[0])
    offsets = {
        'right': [(-amount, 0), (-amount * 2, 0), (-amount * 3, 0)],
        'left': [(amount, 0), (amount * 2, 0), (amount * 3, 0)],
        'up': [(0, amount), (0, amount * 2), (0, amount * 3)],
        'down': [(0, -amount), (0, -amount * 2), (0, -amount * 3)],
    }[direction]
    for index, offset in enumerate(offsets):
        ghost = im.copy()
        alpha = ghost.split()[-1].point(lambda value: int(value * (0.16 / (index + 1))))
        ghost.putalpha(alpha)
        out.alpha_composite(ghost, offset)
    out.alpha_composite(im)
    return out


def save_spritesheet(frames: list[Image.Image], path: Path, cols: int = 8):
    if not frames:
        raise ValueError('no frames')
    normalized = [ensure_canvas(frame) for frame in frames]
    width, height = normalized[0].size
    rows = (len(normalized) + cols - 1) // cols
    sheet = Image.new('RGBA', (width * cols, height * rows), TRANSPARENT)
    for index, frame in enumerate(normalized):
        sheet.alpha_composite(frame, ((index % cols) * width, (index // cols) * height))
    sheet.save(path)


def save_gif(frames: list[Image.Image], path: Path, fps: int = 10):
    duration = int(1000 / max(1, fps))
    normalized = [ensure_canvas(frame) for frame in frames]
    normalized[0].save(
        path,
        save_all=True,
        append_images=normalized[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw
import numpy as np
from pathlib import Path
from typing import Iterable

TRANSPARENT = (0,0,0,0)

def open_rgba(data: bytes) -> Image.Image:
    from io import BytesIO
    im = Image.open(BytesIO(data)).convert('RGBA')
    return im

def fit_sprite(im: Image.Image, size=256, padding=18) -> Image.Image:
    im = im.convert('RGBA')
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    max_side = size - padding * 2
    im.thumbnail((max_side, max_side), Image.Resampling.NEAREST)
    canvas = Image.new('RGBA', (size, size), TRANSPARENT)
    canvas.alpha_composite(im, ((size-im.width)//2, (size-im.height)//2))
    return canvas

def remove_bg_corner(im: Image.Image, tolerance=22) -> Image.Image:
    im = im.convert('RGBA')
    arr = np.array(im)
    corners = np.array([arr[0,0,:3], arr[0,-1,:3], arr[-1,0,:3], arr[-1,-1,:3]], dtype=np.int16)
    bg = np.median(corners, axis=0)
    diff = np.linalg.norm(arr[:,:,:3].astype(np.int16)-bg, axis=2)
    mask = diff < tolerance
    # only remove connected-ish large flat background: soften with edges left intact
    arr[:,:,3] = np.where(mask, 0, arr[:,:,3])
    return Image.fromarray(arr, 'RGBA')

def add_outline(im: Image.Image, color=(20,20,28,255), radius=2) -> Image.Image:
    alpha = im.split()[-1]
    grown = alpha.filter(ImageFilter.MaxFilter(radius*2+1))
    outline = Image.new('RGBA', im.size, color)
    outline.putalpha(ImageChops.subtract(grown, alpha))
    out = Image.new('RGBA', im.size, TRANSPARENT)
    out.alpha_composite(outline)
    out.alpha_composite(im)
    return out

def add_shadow(im: Image.Image, y=226) -> Image.Image:
    # Create a soft shadow derived from the sprite's alpha channel (alternate implementation)
    size = im.size[0]
    out = Image.new('RGBA', im.size, TRANSPARENT)
    alpha = im.split()[-1]
    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(radius=max(3, size // 48)))
    shadow_mask = shadow_mask.point(lambda v: int(v * 0.28))
    shadow = Image.new('RGBA', im.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_mask)
    offset_y = max(2, size // 40)
    out.alpha_composite(shadow, (0, offset_y))
    out.alpha_composite(im)
    return out

def affine(im: Image.Image, scale_x=1, scale_y=1, shear=0, angle=0, translate=(0,0)) -> Image.Image:
    size = im.size[0]
    cx = cy = size/2
    layer = Image.new('RGBA', im.size, TRANSPARENT)
    # scale around center by resizing bbox-ish whole image for pixel-art simplicity
    nw = max(1, int(size*scale_x)); nh = max(1, int(size*scale_y))
    tmp = im.resize((nw, nh), Image.Resampling.NEAREST)
    if shear:
        tmp = tmp.transform(tmp.size, Image.Transform.AFFINE, (1, shear, 0, 0, 1, 0), resample=Image.Resampling.NEAREST)
    if angle:
        tmp = tmp.rotate(angle, resample=Image.Resampling.NEAREST, expand=True)
    x = int(cx - tmp.width/2 + translate[0]); y = int(cy - tmp.height/2 + translate[1])
    layer.alpha_composite(tmp, (x,y))
    return layer

def motion_blur_like(im: Image.Image, direction='right', amount=1) -> Image.Image:
    out = Image.new('RGBA', im.size, TRANSPARENT)
    offsets = {'right': [(-amount,0),(-amount*2,0)], 'left': [(amount,0),(amount*2,0)], 'up': [(0,amount),(0,amount*2)], 'down': [(0,-amount),(0,-amount*2)]}[direction]
    for i, off in enumerate(offsets):
        ghost = im.copy(); a = ghost.split()[-1].point(lambda v: int(v*(0.12/(i+1))))
        ghost.putalpha(a); out.alpha_composite(ghost, off)
    out.alpha_composite(im)
    return out

def save_spritesheet(frames: list[Image.Image], path: Path, cols=8):
    if not frames: raise ValueError('no frames')
    w,h = frames[0].size; rows = (len(frames)+cols-1)//cols
    sheet = Image.new('RGBA', (w*cols, h*rows), TRANSPARENT)
    for i, fr in enumerate(frames):
        sheet.alpha_composite(fr, ((i%cols)*w, (i//cols)*h))
    sheet.save(path)

def save_gif(frames: list[Image.Image], path: Path, fps=10):
    # Composite on checker-safe transparent palette. GIF transparency is limited but works for preview.
    duration = int(1000/max(1,fps))
    pal_frames = []
    for fr in frames:
        pal_frames.append(fr.convert('RGBA'))
    pal_frames[0].save(path, save_all=True, append_images=pal_frames[1:], duration=duration, loop=0, disposal=2, transparency=0)
