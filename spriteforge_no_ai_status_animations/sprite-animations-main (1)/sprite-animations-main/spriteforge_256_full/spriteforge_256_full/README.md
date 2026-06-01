# SpriteForge 256

SpriteForge 256 is a browser-based, CPU-only sprite animation tool. Upload a character sprite, choose an animation, then download individual frames, a GIF preview, or a spritesheet.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Built-in animations

Movement/action: `idle`, `walk`, `run`, `jump`, `attack`, `ranged`, `cast`, `spin`, `bounce`, `custom`.

Reusable game-status effects: `damage`/`hurt`, `heal`, `buff`, `shield`, and `poison`. These are intentionally lightweight and reusable: damage uses knockback plus a transparent red sprite flash; healing uses a soft glow plus a light/white transparent flash; the other effects reuse the same tint/glow helpers with different colors and small motion.

## Notes

- The canvas is normalized to 256×256.
- The app uses deterministic PIL-based transforms, tints, and glows.
- No AI endpoint, AI dependency file, or AI UI toggle is included in this build.
