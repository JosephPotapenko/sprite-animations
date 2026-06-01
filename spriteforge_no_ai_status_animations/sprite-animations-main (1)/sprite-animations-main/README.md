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

For full setup notes and API details, see the nested README in the fixed app folder.
