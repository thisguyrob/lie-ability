# Docker Guide

> **Goal:** Provide a friction‑free way to run Lie‑Ability locally, in CI, or in production with a single command while keeping image sizes lean and rebuilds fast.

---

## 1 · Container Strategy

| Layer                  | Image                                | Purpose                                       |
| ---------------------- | ------------------------------------ | --------------------------------------------- |
| **Backend**            | `ghcr.io/lie-ability/backend:<tag>`  | FastAPI + Uvicorn ASGI server                 |
| **Frontend (runtime)** | `ghcr.io/lie-ability/frontend:<tag>` | Nginx serving the Vite‑built static bundle    |
| **Database**           | `postgres:16-alpine` *(dev prod)*    | Persistent game / user data                   |
| **Cache / PubSub**     | `redis:7-alpine`                     | WebSocket fan‑out & presence heartbeats       |
| **Docs** *(optional)*  | `ghcr.io/lie-ability/docs:<tag>`     | MkDocs‑Material site for GitHub Pages preview |

### Tagging Convention

* `latest` – most recent successful `main` build
* `sha‑<7>` – each commit SHA
* `vX.Y.Z` – semver releases

---

## 2 · Image Blueprint

### 2.1 Backend (`backend/Dockerfile`)

```dockerfile
# ── build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS build
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/poetry.lock ./
RUN pip install --no-cache-dir poetry && poetry export -f requirements.txt > reqs.txt \
 && pip install --no-cache-dir -r reqs.txt
COPY backend .
RUN pytest -q

# ── runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app
ENV PORT=8000
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /app /app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

*Tests run in the build stage; if they fail, the image fails to build.*

### 2.2 Frontend (`frontend/Dockerfile`)

```dockerfile
# builder
FROM node:22-slim AS build
WORKDIR /spa
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev
COPY frontend .
RUN npm run build  # outputs to ./dist

# runtime
FROM nginx:1.27-alpine
COPY --from=build /spa/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
```

### 2.3 Docs (`docs/Dockerfile`)

```dockerfile
FROM python:3.12-slim
WORKDIR /docs
RUN pip install --no-cache mkdocs-material
COPY docs .
CMD ["mkdocs", "serve", "-a", "0.0.0.0:8002"]
```

---

## 3 · Compose Stacks

### 3.1 Dev (`docker-compose.yml`)

```yaml
services:
  backend:
    build: ./backend
    environment:
      - APP_ENV=dev
    volumes:
      - ./backend:/app/backend:rw
    ports: ["8000:8000"]
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    environment:
      - APP_ENV=dev
    volumes:
      - ./frontend:/spa/frontend:rw  # Vite HMR
    ports: ["5173:80"]

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=lie
      - POSTGRES_PASSWORD=ability
      - POSTGRES_DB=lieability
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes: [redisdata:/data]

volumes: { pgdata: {}, redisdata: {} }
```

*Bind mounts enable hot‑reload; remove them in production to freeze the FS.*

### 3.2 Prod (`docker-compose.prod.yml`)

```yaml
services:
  backend:
    image: ghcr.io/lie-ability/backend:latest
    env_file: .env
    deploy:
      replicas: 2
      restart_policy: { condition: on-failure }
  frontend:
    image: ghcr.io/lie-ability/frontend:latest
    ports: ["80:80"]
  db:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
volumes: { pgdata: {} }
```

Run with:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 4 · Commands Cheat Sheet

| Task              | Command                                                                 |
| ----------------- | ----------------------------------------------------------------------- |
| Build images      | `docker compose build`                                                  |
| Start stack       | `docker compose up`                                                     |
| Rebuild & start   | `docker compose up --build`                                             |
| Start prod stack  | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| Stop & cleanup    | `docker compose down -v --remove-orphans`                               |
| Tail logs         | `docker compose logs -f backend`                                        |
| Exec into backend | `docker compose exec backend bash`                                      |

---

## 5 · Environment Variable Injection

1. Copy `.env.example` → `.env` at repo root.
2. Compose passes `env_file: .env` to every service.
3. Secrets (JWT signing key, DB password) can be overridden in CI using `docker compose config`.

---

## 6 · Publishing Images (GitHub Actions)

`.github/workflows/docker.yml` builds & pushes on every merge to `main`:

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: docker/setup-buildx-action@v3
  - uses: docker/login-action@v3
    with:
      registry: ghcr.io
      username: ${{ github.repository_owner }}
      password: ${{ secrets.GITHUB_TOKEN }}
  - uses: docker/build-push-action@v5
    with:
      context: .
      push: true
      tags: ghcr.io/${{ github.repository_owner }}/backend:${{ github.sha }}
```

---

## 7 · Debugging Inside Containers

| Symptom               | Fix                                                                        |
| --------------------- | -------------------------------------------------------------------------- |
| “module not found”    | Verify `COPY` path in Dockerfile; rebuild w/ `--no-cache`.                 |
| Hot reload not firing | Ensure volume mount path matches container workdir.                        |
| File permissions      | Add `:cached` on macOS or `chown -R 1000:1000` in Dockerfile.              |
| DB perms denied       | Remove `pgdata` volume & recreate (`docker volume rm lie-ability_pgdata`). |

---

## 8 · Optimizing Image Size

* Use `python:*-slim` and `apt-get purge` build deps.
* Layer caching: copy `poetry.lock` **before** source files.
* Strip Node dev deps: `npm ci --omit=dev`.
* Multi‑stage build eliminates compiled artefacts.

Final sizes:

| Image    | Size     |
| -------- | -------- |
| backend  | \~165 MB |
| frontend | \~35 MB  |
| docs     | \~55 MB  |

---

## 9 · WSL‑2 / Windows Notes

* Enable Docker Desktop WSL integration.
* Clone repo in Linux path (`/home/<user>/lie-ability`).
* Use `wsl ~ -d Ubuntu-22.04` to run CLI.

---

## 10 · Frequently Asked Questions

> **Q: How do I reset everything?**
> `docker compose down -v --remove-orphans && docker system prune -af`.

> **Q: Can I run only the backend for API testing?**
> `docker compose up backend db redis`.

> **Q: Can I disable Redis?**
> Yes in dev: set `USE_REDIS=false` in `.env` and comment out the service; the server falls back to in‑process fan‑out.

---

👍 You’re container‑ready!  File issues if you spot any leaky layers or build slowness.