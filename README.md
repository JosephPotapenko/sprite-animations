# SpriteForge 256

SpriteForge 256 is a browser-based sprite animation tool that runs well in GitHub Codespaces and on a normal CPU-only machine.

There are now two copies in the repo:

- [spriteforge_256_full/spriteforge_256_full](spriteforge_256_full/spriteforge_256_full) is the original app tree.
- [sprite-animations-main-fixed/sprite-animations-main/spriteforge_256_full/spriteforge_256_full](sprite-animations-main-fixed/sprite-animations-main/spriteforge_256_full/spriteforge_256_full) is the fixed tree.

Use the fixed tree in Codespaces. Open a terminal there, then run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If you prefer the older one-command dev server, `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` also works.

## Vercel deployment

This repo now includes a Vercel entrypoint at [`api/index.py`](api/index.py) plus a [`vercel.json`](vercel.json) router and a root [`requirements.txt`](requirements.txt).

To deploy:

1. Push the repo to GitHub.
2. Import the repository into Vercel.
3. Keep the root directory as-is.
4. Vercel will install the Python dependencies and serve the FastAPI app automatically.

The website will work without manually starting `uvicorn`. On Vercel, generated previews and downloads are returned inline, so the site does not depend on persistent local files.

For full setup notes and API details, see the nested README in the fixed app folder.
