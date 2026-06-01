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


def test_generate_endpoint_supports_status_effect_animations(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUTS', tmp_path / 'outputs')
    monkeypatch.setattr(main, 'UPLOADS', tmp_path / 'uploads')
    main.OUTPUTS.mkdir(parents=True, exist_ok=True)
    main.UPLOADS.mkdir(parents=True, exist_ok=True)

    client = TestClient(main.app)
    response = client.post(
        '/api/generate',
        files={'sprite': ('sprite.png', make_sprite(), 'image/png')},
        data={
            'animation': 'damage',
            'frames': '4',
            'fps': '10',
            'pixel_size': '256',
            'spritesheet_columns': '2',
            'remove_background': 'false',
            'outline': 'false',
            'shadow': 'true',
            'smart_prompt': 'true',
            'seed': '7',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['animation'] == 'damage'
    assert payload['frames'] == 4
