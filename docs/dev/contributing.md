# Contributing Guide

> **Thank you for helping build Lie‑Ability!**  We welcome code, design, docs, prompts, and play‑testing feedback.  This guide explains our workflow, coding standards, and how we collaborate with the OpenAI **Codex** agent.

---

## 1 · Ground Rules

1. **Be kind & constructive.**  We follow the [Contributor Covenant](https://contributor-covenant.org/version/2/1/code_of_conduct/).
2. **No spoilers.**  Don’t submit copyrighted trivia prompts.
3. **Respect the license (CC BY‑NC 4.0)** — your PR means you agree to release your contribution under the same terms.

---

## 2 · How We Work

### 2.1 Issue → Spec → PR

| Step                                   | Action                                           | Who           |
| -------------------------------------- | ------------------------------------------------ | ------------- |
| ① Draft **Issue**                      | Describe bug/feature; use templates.             | Contributor   |
| ② Attach or update **spec** in `docs/` | Markdown; diagrams welcome.                      | Author        |
| ③ Label `codex-task` *(optional)*      | Signals that we want the Codex bot to open a PR. | Maintainer    |
| ④ **Pull Request**                     | AI or human writes code; links the issue.        | Codex / Human |
| ⑤ **Review**                           | Two maintainers approve; CI green.               | Humans        |
| ⑥ **Merge**                            | Squash & merge to `main`.                        | Maintainer    |

> **Note:** Small typo / doc fixes can skip the issue and go straight to a PR.

### 2.2 Branch Naming

```
feature/<short-desc>
bugfix/<ticket-#>
chore/<scope>
docs/<topic>
```

### 2.3 Commit Messages (Conventional Commits)

```
feat(player): add avatar selector
fix(api): prevent vote on own lie
```

*Use imperative mood; body line length ≤72 chars.*

---

## 3 · Code Style & Tooling

| Language           | Formatter / Linter             | Rules                          |
| ------------------ | ------------------------------ | ------------------------------ |
| Python             | **Black** (line 88) & **Ruff** | `make lint` or pre‑commit hook |
| TypeScript / React | **ESLint** + **Prettier**      | Airbnb + Prettier config       |
| Markdown           | **Prettier**                   | wrap prose @ 80 cols           |
| YAML               | **yamllint**                   | relaxed                        |

Pre‑commit hooks run automatically; install them with:

```bash
pre-commit install
```

---

## 4 · Tests

* **Python**: `pytest` + `pytest‑asyncio`.
* **Frontend**: `Vitest` + `@testing‑library/react`.
* Write tests for any new logic or failing bug.
* Target **≥90 % coverage** on changed lines (CI will comment).

Run everything:

```bash
make test
```

---

## 5 · Pull Request Checklist

* [ ] Linked to an issue (`Fixes #123`).
* [ ] CI green (lint + tests + type‑check).
* [ ] Docs or comments updated.
* [ ] For UI changes: screenshot/GIF in PR description.
* [ ] No sensitive data added to repo or logs.

Large features: draft PR early to gather feedback.

---

## 6 · Codex Integration

1. Maintainers tag an issue with **`codex-task`**.
2. The Codex GitHub App generates a PR referencing the spec.
3. Reviewers treat Codex like any other contributor: request changes, test locally, and ensure style compliance.
4. If Codex stalls, humans can push commits to the PR branch or close it.

---

## 7 · Development Environment

Follow [`dev/setup.md`](./setup.md) for local bootstrap, or use the **VS Code devcontainer** for one‑click hacking.

---

## 8 · Community & Support

| Channel                   | Purpose                           |
| ------------------------- | --------------------------------- |
| GitHub **Discussions**    | Feature ideas, Q\&A.              |
| Discord `#lieability-dev` | Real‑time chat, pairing sessions. |
| Issues                    | Bugs & actionable tasks only.     |

---

## 9 · Release Flow

1. Merge to `main` triggers CI → **`latest`** Docker images.
2. Maintainer tags `vX.Y.Z` → GitHub Release notes auto‑generated.
3. `mkdocs gh‑deploy` publishes docs site.

---

## 10 · Thanks!

Your creativity keeps Lie‑Ability fresh.  Whether you craft devilish prompts, sleek components, or rock‑solid tests — **we appreciate you.**  Now go write some code (or lies) and open that PR 🚀
