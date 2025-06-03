# Developer Setup Guide

> **Target OS:** macOS (Apple Silicon & Intel) and modern Linux distros (Ubuntu 22.04+, Fedora 39+).  Windows users can follow WSL‑2 instructions at the end.

---

## 1 · Prerequisites

| Tool                            | Version  | Install Command                                           |
| ------------------------------- | -------- | --------------------------------------------------------- |
| **Git**                         | ≥ 2.40   | `brew install git` / `apt install git`                    |
| **Python**                      | 3.12.x   | `brew install python@3.12` / `asdf install python 3.12.2` |
| **Node.js**                     | 22.x LTS | `brew install node` / `asdf install nodejs 22.2.0`        |
| **Docker Desktop** *(optional)* | 4.29+    | [docker.com](https://www.docker.com/)                     |
| **Make** *(optional)*           | any      | `brew install make` / `apt install make`                  |

> **Tip:** We use [asdf](https://asdf-vm.com/) in CI to pin exact versions.  A `.tool-versions` file is provided.

---

## 2 · Clone & Bootstrap

```bash
# 1 • Clone
$ git clone https://github.com/thisguyrob/lie-ability.git && cd lie-ability

# 2 • Python venv
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install -r backend/requirements.txt

# 3 • Node packages
$ cd frontend && npm ci && cd ..

# 4 • Pre‑commit hooks (black, ruff, prettier, eslint)
$ pre-commit install
```

CI runs `black --check`, `ruff`, `mypy`, `eslint`, and `prettier --check` on every commit.

---

## 3 · Running the App (Native)

```bash
# 1 • backend (FastAPI + Uvicorn reload)
$ uvicorn backend.main:app --reload &

# 2 • frontend (Vite hot reload)
$ cd frontend && npm run dev &

# 3 • Open your browser
# Player view: http://localhost:5173
# Shared display: http://localhost:5173/shared
```

The root convenience script picks this flow for you:

```bash
./start.sh -n    # -n = native (no Docker)
```

---

## 4 · Running in Docker Compose

```bash
# Build & start all services (backend, frontend, postgres, redis)
$ docker compose up --build

# Tail logs
$ docker compose logs -f backend
```

Once running:

* API Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
* Player View: [http://localhost](http://localhost)

Stop & prune:

```bash
$ docker compose down -v   # removes volumes
```

---

## 5 · Environment Variables

Create a `.env` file at the repo root; copy from the template:

```bash
$ cp .env.example .env
# edit values as needed
```

Key vars:

```dotenv
APP_ENV=dev            # dev | prod
DATABASE_URL=sqlite:///lieability.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=please_change_me
```

Docker Compose reads the same file.

---

## 6 · Tests & Linting

```bash
# Python unit tests
$ pytest -q

# Frontend tests (Vitest)
$ cd frontend && npm test

# Full lint suite
$ make lint     # or ./scripts/lint_all.sh
```

Coverage reports land in `./coverage/`.

---

## 7 · Database Migrations

We use **Alembic**:

```bash
$ alembic revision --autogenerate -m "add rounds table"
$ alembic upgrade head
```

SQLite in dev; PostgreSQL in Docker/prod.

---

## 8 · Debugging Tips

* Use VS Code **`launch.json`** presets for breakpoints (pre‑configured).
* Navigate to [http://localhost:8000/redoc](http://localhost:8000/redoc) to inspect live schemas.
* Run `docker compose exec backend bash` to poke inside the container.

---

## 9 · Hot Reload Matrix

| Stack        | Hot Reload?           | Trigger                   |
| ------------ | --------------------- | ------------------------- |
| **Backend**  | ✅ `uvicorn --reload`  | Python/HTML/Jinja changes |
| **Frontend** | ✅ `vite`              | TS/JS/TSX/MDX/CSS changes |
| **Docs**     | ✅ MkDocs’ live server | Markdown in `docs/`       |

---

## 10 · VS Code Devcontainer *(optional)*

The repository includes a `.devcontainer` folder.

```bash
# inside VS Code
> Remote‑Containers: Reopen in Container
```

The container mirrors CI (Python + Node + Docker‑in‑Docker).

---

## 11 · Git Hooks Cheat Sheet

| Hook         | Purpose                         |
| ------------ | ------------------------------- |
| `pre-commit` | black + ruff + prettier --write |
| `pre-push`   | pytest + vitest + mypy + eslint |

Skip with `--no-verify` only for emergency fixes.

---

## 12 · Windows / WSL‑2 Notes

1. Install Ubuntu 22.04 from MS Store.
2. Follow Linux instructions above inside the WSL shell.
3. Expose port 5173 to Windows via: `wsl --shutdown && wsl -d Ubuntu-22.04`.

---

## 13 · Common Make Targets

```Makefile
.PHONY: dev test lint db-reset

dev:           # Native backend + frontend + docs
	tmux new -s dev \
	  'uvicorn backend.main:app --reload' \; \
	  split-window -h 'cd frontend && npm run dev' \; \
	  split-window -v 'mkdocs serve'

test: pytest vitest
lint: ruff mypy eslint prettier
```

---

You’re ready to ship lies!  Ping `@maintainers` on Discord if you hit snags.  Happy coding 🚀