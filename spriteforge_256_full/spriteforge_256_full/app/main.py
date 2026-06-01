from __future__ import annotations

import base64
import json
import os
from io import BytesIO
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from PIL import Image

from .engine.animation import SpriteAnimator
from .engine.image_ops import (
    CANVAS_SIZE,
    add_outline,
    add_shadow,
    ensure_canvas,
    fit_sprite,
    open_rgba,
    remove_bg_corner,
    save_gif,
    save_spritesheet,
)
from .engine.prompt import parse_prompt
from .schemas import GenerateRequest

BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
IS_VERCEL = bool(os.getenv('VERCEL'))
if IS_VERCEL:
    OUTPUTS = Path('/tmp/spriteforge_256/outputs')
    UPLOADS = Path('/tmp/spriteforge_256/uploads')
else:
    OUTPUTS = ROOT / 'outputs'
    UPLOADS = ROOT / 'uploads'
    OUTPUTS.mkdir(exist_ok=True)
    UPLOADS.mkdir(exist_ok=True)

def _image_to_data_uri(image: Image.Image, fmt: str = 'PNG') -> str:
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    mime = 'image/png' if fmt.upper() == 'PNG' else 'image/gif' if fmt.upper() == 'GIF' else 'application/octet-stream'
    return f'data:{mime};base64,{encoded}'

def _bytes_to_data_uri(payload: bytes, mime: str) -> str:
    return f'data:{mime};base64,{base64.b64encode(payload).decode("ascii")}'

app = FastAPI(title='SpriteForge 256', version='1.0.0')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
app.mount('/outputs', StaticFiles(directory=OUTPUTS), name='outputs')
templates = Jinja2Templates(directory=BASE_DIR / 'templates')


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/health')
def health():
    return {'ok': True, 'name': 'SpriteForge 256', 'canvas_size': CANVAS_SIZE}


@app.get('/api/status')
def status():
    return health()


def _normalize_frames(frames_out):
    return [ensure_canvas(frame, CANVAS_SIZE) for frame in frames_out]


@app.post('/api/generate')
async def generate(
    sprite: UploadFile = File(...),
    animation: str = Form('walk'),
    prompt: str = Form(''),
    frames: int = Form(8),
    fps: int = Form(10),
    pixel_size: int = Form(256),
    spritesheet_columns: int = Form(8),
    remove_background: bool = Form(False),
    outline: bool = Form(False),
    shadow: bool = Form(True),
    smart_prompt: bool = Form(True),
    seed: str = Form(''),
):
    try:
        req = GenerateRequest(
            animation=animation if animation in ['idle', 'walk', 'run', 'jump', 'attack', 'ranged', 'cast', 'hurt', 'damage', 'heal', 'buff', 'shield', 'poison', 'spin', 'bounce'] else 'walk',
            prompt=prompt,
            frames=frames,
            fps=fps,
            pixel_size=pixel_size,
            spritesheet_columns=spritesheet_columns,
            remove_background=remove_background,
            outline=outline,
            shadow=shadow,
            smart_prompt=smart_prompt,
            seed=int(seed) if str(seed).strip() else None,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    raw = await sprite.read()
    if not raw:
        raise HTTPException(400, 'No image uploaded.')

    try:
        im = open_rgba(raw)
    except Exception as exc:
        raise HTTPException(400, 'Upload must be a readable image file.') from exc

    if req.remove_background:
        im = remove_bg_corner(im)

    base = fit_sprite(im, CANVAS_SIZE)
    if req.outline:
        base = add_outline(base)

    settings = parse_prompt(req.prompt, req.animation, req.frames, req.fps) if req.smart_prompt else parse_prompt('', req.animation, req.frames, req.fps)
    settings.frames = req.frames if not any(x in (req.prompt or '').lower() for x in ['frame', 'frames']) else settings.frames
    settings.fps = req.fps if 'fps' not in (req.prompt or '').lower() else settings.fps

    animator = SpriteAnimator(base, settings, req.seed)
    frames_out = _normalize_frames(animator.generate())
    if req.shadow:
        frames_out = [add_shadow(frame) for frame in frames_out]
    frames_out = _normalize_frames(frames_out)

    # Detect whether the original upload had any transparency; if so, keep outputs transparent
    try:
        has_transparency = im.getchannel('A').getextrema()[0] < 255
    except Exception:
        has_transparency = False

    job = uuid.uuid4().hex[:12]
    out_dir = OUTPUTS / job
    out_dir.mkdir(parents=True, exist_ok=True)

    if IS_VERCEL:
        gif_buffer = BytesIO()
        normalized = [ensure_canvas(frame, CANVAS_SIZE) for frame in frames_out]
        duration = int(1000 / max(1, settings.fps))
        normalized[0].save(
            gif_buffer,
            format='GIF',
            save_all=True,
            append_images=normalized[1:],
            duration=duration,
            loop=0,
            disposal=2,
            optimize=False,
        )
        sheet_buffer = BytesIO()
        width, height = normalized[0].size
        rows = (len(normalized) + req.spritesheet_columns - 1) // req.spritesheet_columns
        sheet = Image.new('RGBA', (width * req.spritesheet_columns, height * rows), (0, 0, 0, 0))
        for index, frame in enumerate(normalized):
            sheet.alpha_composite(frame, ((index % req.spritesheet_columns) * width, (index // req.spritesheet_columns) * height))
        sheet.save(sheet_buffer, format='PNG')

        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w', ZIP_DEFLATED) as zf:
            for index, frame in enumerate(normalized):
                frame_bytes = BytesIO()
                frame.save(frame_bytes, format='PNG')
                zf.writestr(f'frame_{index:03d}.png', frame_bytes.getvalue())

        preview_png_data = _image_to_data_uri(normalized[0], 'PNG') if has_transparency else None
        metadata = {
            'job_id': job,
            'animation': settings.animation,
            'frames': len(frames_out),
            'fps': settings.fps,
            'canvas_size': CANVAS_SIZE,
            'pixel_size': req.pixel_size,
            'prompt': req.prompt,
            'downloads': {
                'gif': _bytes_to_data_uri(gif_buffer.getvalue(), 'image/gif'),
                'spritesheet': _bytes_to_data_uri(sheet_buffer.getvalue(), 'image/png'),
                'zip': _bytes_to_data_uri(zip_buffer.getvalue(), 'application/zip'),
            },
        }
        if preview_png_data:
            metadata['downloads']['preview_png'] = preview_png_data
        return JSONResponse(metadata)

    frames_dir = out_dir / 'frames'
    frames_dir.mkdir()

    for index, frame in enumerate(frames_out):
        frame.save(frames_dir / f'frame_{index:03d}.png')

    sheet_path = out_dir / 'spritesheet.png'
    gif_path = out_dir / 'preview.gif'
    preview_png_path = out_dir / 'preview.png'
    zip_path = out_dir / 'frames.zip'
    save_spritesheet(frames_out, sheet_path, req.spritesheet_columns)
    save_gif(frames_out, gif_path, settings.fps)

    # If the input had transparency, also produce a PNG preview that preserves alpha
    if has_transparency:
        try:
            frames_out[0].save(preview_png_path)
        except Exception:
            pass

    with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zf:
        for path in frames_dir.glob('*.png'):
            zf.write(path, arcname=path.name)

    metadata = {
        'job_id': job,
        'animation': settings.animation,
        'frames': len(frames_out),
        'fps': settings.fps,
        'canvas_size': CANVAS_SIZE,
        'pixel_size': req.pixel_size,
        'prompt': req.prompt,
        'downloads': {
            'gif': f'/outputs/{job}/preview.gif',
            'spritesheet': f'/outputs/{job}/spritesheet.png',
            'zip': f'/outputs/{job}/frames.zip',
        },
    }
    if has_transparency:
        metadata['downloads']['preview_png'] = f'/outputs/{job}/preview.png'
    (out_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return JSONResponse(metadata)


@app.get('/api/jobs/{job_id}')
def job(job_id: str):
    path = OUTPUTS / job_id / 'metadata.json'
    if not path.exists():
        raise HTTPException(404, 'Job not found')
    return json.loads(path.read_text())


@app.get('/download/{job_id}/{kind}')
def download(job_id: str, kind: str):
    mapping = {'gif': 'preview.gif', 'spritesheet': 'spritesheet.png', 'zip': 'frames.zip', 'metadata': 'metadata.json'}
    if kind not in mapping:
        raise HTTPException(404, 'Unknown download kind')
    path = OUTPUTS / job_id / mapping[kind]
    if not path.exists():
        raise HTTPException(404, 'File not found')
    return FileResponse(path, filename=f'spriteforge_{job_id}_{mapping[kind]}')
