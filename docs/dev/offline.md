# Offline Development & CI

Running the project without Internet requires pre-downloading all dependencies.

## 1 \xc2\xb7 Prep Script

Execute `scripts/prep_env.sh` **while online**. It downloads Python wheels and npm packages to `.cache/` and builds `.venv/`. The frontend production bundle is also compiled.

## 2 \xc2\xb7 Caching

Commit the `.cache/pip/` and `.cache/npm/` directories or store them as CI artifacts. Optionally commit `.venv/` and `frontend/node_modules/` if your CI can't restore caches.

## 3 \xc2\xb7 Installing

```bash
python -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links=.cache/pip -r backend/requirements.txt
cd frontend
npm ci --prefer-offline --no-audit --progress=false
```

## 4 \xc2\xb7 Workflow Tips

Run all build and test steps after the dependencies are installed from local sources. Ensure `prep_env.sh` runs only when Internet access is available.
