from __future__ import annotations

import json
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

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
OUTPUTS = ROOT / 'outputs'
UPLOADS = ROOT / 'uploads'
OUTPUTS.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)


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
            animation=animation if animation in ['idle', 'walk', 'run', 'jump', 'attack', 'ranged', 'cast', 'hurt', 'damage', 'heal', 'buff', 'shield', 'poison', 'spin', 'bounce', 'custom'] else 'custom',
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

    job = uuid.uuid4().hex[:12]
    out_dir = OUTPUTS / job
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / 'frames'
    frames_dir.mkdir()

    for index, frame in enumerate(frames_out):
        frame.save(frames_dir / f'frame_{index:03d}.png')

    sheet_path = out_dir / 'spritesheet.png'
    gif_path = out_dir / 'preview.gif'
    zip_path = out_dir / 'frames.zip'
    save_spritesheet(frames_out, sheet_path, req.spritesheet_columns)
    save_gif(frames_out, gif_path, settings.fps)

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
    (out_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return JSONResponse(metadata)


@app.get('/download/{job_id}/{kind}')
def download(job_id: str, kind: str):
    mapping = {'gif': 'preview.gif', 'spritesheet': 'spritesheet.png', 'zip': 'frames.zip', 'metadata': 'metadata.json'}
    if kind not in mapping:
        raise HTTPException(404, 'Unknown download kind')
    path = OUTPUTS / job_id / mapping[kind]
    if not path.exists():
        raise HTTPException(404, 'File not found')
    return FileResponse(path, filename=f'spriteforge_{job_id}_{mapping[kind]}')
