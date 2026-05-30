# SpriteForge 256

SpriteForge 256 is a browser-based sprite animation tool that runs well in GitHub Codespaces and on a normal CPU-only machine. Upload one character sprite, generate a 256×256 animation, preview it in the browser, and download the result as a GIF, PNG spritesheet, or ZIP of PNG frames.

## What it does

- Upload PNG, JPG, or WebP sprite art
- Normalize every output frame to an exact 256×256 canvas
- Generate procedural animations for `idle`, `walk`, `run`, `jump`, `attack`, `cast`, `hurt`, `spin`, `bounce`, and `custom`
- Parse simple prompts like `fast sword attack, 12 frames`
- Download an animated GIF, a PNG spritesheet, or a ZIP of frames
- Use a prompt-based CPU AI fallback by default, with optional diffusion only when explicitly enabled

## One-command start in Codespaces

The repository ships with a root-level devcontainer. Open the repo in Codespaces, wait for dependency install, then run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the forwarded port `8000`.

## Local setup

```bash
cd spriteforge_256_full/spriteforge_256_full
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker setup

From the repository root:

```bash
docker build -t spriteforge-256 .
docker run -p 8000:8000 spriteforge-256
```

## How to use the app

1. Open the website in your browser.
2. Upload a sprite with a transparent background if possible.
3. Choose an animation or describe one in the prompt.
4. Click Generate animation.
5. Preview the GIF, then download the GIF, spritesheet, or ZIP of frames.

## CPU-only limits

The default engine is intentionally lightweight and free. It uses procedural transforms, timing curves, and simple effects instead of pose estimation or diffusion models. That keeps it fast in Codespaces, but it also means:

- It cannot infer detailed limb motion from a single flat sprite.
- It works best when the input sprite already faces a consistent direction.
- Complex cloth, weapon, and facial changes are approximated rather than redrawn.
- GIF output is less faithful than the PNG spritesheet or ZIP because of GIF color limits.

## Optional AI upgrade path

Prompt-based AI generation is wired into the UI behind the `Use prompt-based AI fallback` checkbox. It works by default on CPU and does not download large models. It reads the prompt, picks a motion style, applies procedural motion, and adds prompt-guided color/energy styling.

On larger machines you can opt into the experimental diffusion backend with `SPRITEFORGE_AI_BACKEND=diffusion`, and you can override the model with `SPRITEFORGE_AI_MODEL_ID`. Install the extra dependencies with:

```bash
pip install -r requirements-ai.txt
```

That path is intentionally not required for the normal CPU animation mode or the prompt-based fallback.

Suggested open-source directions if you want to extend the project later:

- Diffusers image-to-image pipelines for restyling
- ControlNet for pose and silhouette control
- AnimateDiff or a motion adapter for temporal coherence

Check the model license before using any trained model commercially.

## Repository layout

```text
app/
  main.py                 FastAPI app and API routes
  schemas.py              Validation models
  engine/
    animation.py          Procedural animation engine
    image_ops.py          Sprite normalization/export helpers
    prompt.py             Prompt parser
  ai/
    optional_diffusion.py Optional GPU model hook
  static/
    app.js
    styles.css
  templates/
    index.html
```

## API

`POST /api/generate`

Multipart form fields:

- `sprite`: image file
- `animation`: idle/walk/run/jump/attack/cast/hurt/spin/bounce/custom
- `prompt`: optional natural language prompt
- `frames`: 2-32
- `fps`: 1-30
- `pixel_size`: accepted for compatibility, but output is always normalized to 256×256
- `spritesheet_columns`: 1-16
- `remove_background`: true/false
- `outline`: true/false
- `shadow`: true/false
- `smart_prompt`: true/false
- `seed`: optional int

Returns JSON with URLs for generated files and metadata about the job.
