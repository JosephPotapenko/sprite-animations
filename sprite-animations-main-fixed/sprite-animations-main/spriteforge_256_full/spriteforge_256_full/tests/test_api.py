from __future__ import annotations

import io
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import app.main as main


def make_sprite() -> bytes:
    image = Image.new('RGBA', (96, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 16, 76, 110), radius=12, fill=(160, 100, 220, 255))
    draw.rectangle((36, 34, 60, 62), fill=(255, 230, 210, 255))
    draw.rectangle((30, 108, 42, 126), fill=(90, 60, 180, 255))
    draw.rectangle((54, 108, 66, 126), fill=(90, 60, 180, 255))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def test_health_endpoint_reports_canvas_size():
    client = TestClient(main.app)

    response = client.get('/health')

    assert response.status_code == 200
    assert response.json()['ok'] is True
    assert response.json()['canvas_size'] == 256


def test_ai_status_reports_prompt_fallback_by_default():
    client = TestClient(main.app)

    response = client.get('/api/ai/status')

    assert response.status_code == 200
    payload = response.json()
    assert payload['enabled'] is True
    assert payload['available'] is True
    assert payload['model_id'] == 'procedural-prompt-fallback'


def test_ai_generate_endpoint_uses_monkeypatched_generator(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUTS', tmp_path / 'outputs')
    monkeypatch.setattr(main, 'UPLOADS', tmp_path / 'uploads')
    monkeypatch.setattr(main, 'AI_FEATURE_FLAG', True)
    main.OUTPUTS.mkdir(parents=True, exist_ok=True)
    main.UPLOADS.mkdir(parents=True, exist_ok=True)

    from app.ai import optional_diffusion
    from PIL import Image

    def fake_generate_ai_frames(base, prompt, frames=8, size=256, animation='custom', seed=None):
        return [Image.new('RGBA', (size, size), (0, 0, 0, 0)) for _ in range(frames)]

    monkeypatch.setattr(optional_diffusion, 'generate_ai_frames', fake_generate_ai_frames)

    client = TestClient(main.app)
    response = client.post(
        '/api/ai/generate',
        files={'sprite': ('sprite.png', make_sprite(), 'image/png')},
        data={
            'animation': 'cast',
            'prompt': 'glowing spell aura',
            'frames': '4',
            'seed': '9',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'prompt-ai-fallback'
    assert payload['frames'] == 4
    assert client.get(f"/download/{payload['job_id']}/gif").status_code == 200


def test_generate_endpoint_creates_all_downloads(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUTS', tmp_path / 'outputs')
    monkeypatch.setattr(main, 'UPLOADS', tmp_path / 'uploads')
    main.OUTPUTS.mkdir(parents=True, exist_ok=True)
    main.UPLOADS.mkdir(parents=True, exist_ok=True)

    client = TestClient(main.app)
    response = client.post(
        '/api/generate',
        files={'sprite': ('sprite.png', make_sprite(), 'image/png')},
        data={
            'animation': 'walk',
            'frames': '6',
            'fps': '10',
            'pixel_size': '256',
            'spritesheet_columns': '3',
            'remove_background': 'false',
            'outline': 'false',
            'shadow': 'true',
            'smart_prompt': 'true',
            'seed': '42',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['canvas_size'] == 256
    assert payload['frames'] == 6

    gif_response = client.get(f"/download/{payload['job_id']}/gif")
    sheet_response = client.get(f"/download/{payload['job_id']}/spritesheet")
    zip_response = client.get(f"/download/{payload['job_id']}/zip")

    assert gif_response.status_code == 200
    assert sheet_response.status_code == 200
    assert zip_response.status_code == 200

    zip_file = ZipFile(io.BytesIO(zip_response.content))
    assert len(zip_file.namelist()) == 6


def test_ai_generate_prompt_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUTS', tmp_path / 'outputs')
    monkeypatch.setattr(main, 'UPLOADS', tmp_path / 'uploads')
    main.OUTPUTS.mkdir(parents=True, exist_ok=True)
    main.UPLOADS.mkdir(parents=True, exist_ok=True)

    client = TestClient(main.app)
    response = client.post(
        '/api/ai/generate',
        files={'sprite': ('sprite.png', make_sprite(), 'image/png')},
        data={'animation': 'custom', 'prompt': 'fast fire sword attack, 6 frames', 'frames': '6'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['animation'] == 'attack'
    assert payload['frames'] == 6
    assert payload['canvas_size'] == 256
    assert payload['downloads']['gif'].endswith('/preview.gif')
