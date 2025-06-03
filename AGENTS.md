# AGENTS.md

> Guidelines for autonomous coding agents (e.g. OpenAI Codex) contributing to **Lie‑Ability**.

---

## 1  Mission

Your goal is to translate the natural‑language specifications in `docs/` and GitHub issues into well‑tested, merge‑ready code while faithfully following the project’s architecture, gameplay rules, and coding standards.

---

## 2  Repository Landmarks

| Path                 | Purpose                                                                      |
| -------------------- | ---------------------------------------------------------------------------- |
| `/docs/`             | Human‑readable specs (`architecture.md`, `gameplay.md`, …). **Start here.**  |
| `/backend/`          | FastAPI server (`main.py`) and game logic (`game/`).                         |
| `/frontend/`         | React + Vite apps: `shared/` (TV) and `player/` (phones).                    |
| `/prompts/`          | CSV files for prompt packs.                                                  |
| `/tests/`            | Project‑wide integration tests. Backend‑unit tests live in `backend/tests/`. |
| `start.sh`           | Smart launcher: native dev or Docker Compose.                                |
| `docker-compose.yml` | Reference container orchestration.                                           |

---

## 3  Development Environment

### 3.1  Native (macOS/Linux)

```bash
./start.sh --dev  # sets up venv, installs deps, starts backend & frontend with hot‑reload
```

### 3.2  Docker

```bash
docker compose up --build  # replicates CI
```

---

## 4  Test & Lint Commands

| Context                  | Command                                | Notes                                              |
| ------------------------ | -------------------------------------- | -------------------------------------------------- |
| **Backend tests**        | `pytest -q`                            | All new Python code **must** have ≥ 90 % coverage. |
| **Type check**           | `mypy backend/`                        | No type errors allowed.                            |
| **Python lint**          | `ruff .` then `black --check .`        | Auto‑fixable issues may be committed separately.   |
| **Frontend tests**       | `npm test --workspaces`                | CI uses `vitest`.                                  |
| **Frontend lint/format** | `npm run lint && npm run format:check` | ESLint + Prettier.                                 |
| **End‑to‑end**           | `pytest tests/e2e/`                    | Simulates 4 players via WebSocket client.          |

*CI script (`.github/workflows/ci.yml`) executes all rows above in the order shown.*

---

## 5  Branch & Commit Policy

* **Branch name** – `codex/<ticket‑id>/<slug>` (e.g. `codex/42/add-sfx`).
* **Commits** should be atomic and conventionally formatted (`feat:`, `fix:`, `docs:` …).
* **Pull Request description** must reference the GitHub issue and list:

  1. **Changeset summary**
  2. **Testing steps** (commands run + results)
  3. **Screenshots/GIFs** for UI work

---

## 6  Coding Standards

### 6.1  Python

* Follow \[PEP 8] plus `black`’s defaults.
* Use **Pydantic** models for request/response bodies.
* Prefer `async def` endpoints; do not block the event loop.
* All functions require type hints and docstrings (Google style).

### 6.2  TypeScript/React

* Functional components, hooks only – no class components.
* State synced from server via **Socket.IO**. Local state limited to transient UI.
* Tailwind CSS utility classes; avoid inline styles.

### 6.3  Game Logic

* All state changes flow through `GameState` reducer in `backend/game/state.py`.
* Clients treat server state as source of truth – no hidden authority on frontend.

---

## 7  Typical Workflow for a New Feature

1. **Read spec** – start in `docs/` and the linked GitHub issue.
2. **Create branch** – see §5.
3. **Write failing tests** in `backend/tests/` or `frontend/__tests__/`.
4. **Implement code** until tests pass and linting is clean.
5. **Update docs** if public behavior changes (open *separate* `docs:` PR).
6. **Push branch** – CI runs. Fix any failures.
7. **Open PR** – fill template, ensure reviewers are requested.

---

## 8  Prohibited Actions

* Never commit `.env`, secrets, or large binaries (> 20 MB).
* Do not modify `LICENSE`.
* Avoid breaking public API routes without a **major** version bump.
* No force‑push to `main`.

---

## 9  Safety & Rollback

* Database migrations via **Alembic** – include upgrade & downgrade steps.
* Feature flags can be toggled with environment vars (`FEATURE_*`).
* Deploys are atomic: Docker image built on merge to `main` and tagged with SHA.
* If rollback required, redeploy previous image via GitHub Actions workflow.

---

## 10  Help Commands

| Need                 | Command                                        |
| -------------------- | ---------------------------------------------- |
| Re‑generate API docs | `make redoc` → outputs `docs/api_openapi.html` |
| Seed sample data     | `python backend/scripts/seed_prompts.py`       |
| Run interactive REPL | `ipython -i backend/devtools/shell.py`         |

---

## 11  Example Micro‑Tasks for Agents

| Ticket | Example Prompt                       | Expected Outcome                                                    |
| ------ | ------------------------------------ | ------------------------------------------------------------------- |
| `#71`  | *“Add prompt pack: Video Games.csv”* | New CSV in `prompts/`, tests verifying CSV validity.                |
| `#85`  | *“Expose `/healthz` endpoint”*       | FastAPI route + test + docs entry.                                  |
| `#112` | *“Mobile: vibrate on score reveal”*  | Frontend hook using `navigator.vibrate()`, passes lint & unit test. |

---

## 12  Final Checklist Before PR Merge

* [ ] All tests pass (`./start.sh --ci` or CI).
* [ ] Coverage unchanged or improved.
* [ ] Lint & format clean.
* [ ] Docs updated if necessary.
* [ ] Reviewer approval + green CI.

---

### Welcome aboard, Agent 🤖  — happy bluff‑coding!
