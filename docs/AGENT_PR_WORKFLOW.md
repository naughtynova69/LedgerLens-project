# Pre-Requisite Instructions: AI Harness Branching & Pull Request Workflow

> **MANDATORY PRE-REQUISITE FOR ALL AI HARNESSES & MODELS**
>
> Applies to **ZCode (`GLM 5.3`)**, **Antigravity (`Gemini`)**, **Claude Code**, **Codex**, **Cursor**, **Windsurf**, and any other automated coding harness or subagent operating on `naughtynova69/LedgerLens-project`.

---

## 1. Core Rule: Never Commit, Push, or Merge Directly to `main`

The `main` branch of `https://github.com/naughtynova69/LedgerLens-project` is protected by a GitHub repository ruleset (`Protect main`):

- Direct pushes to `main` are **prohibited**.
- Force pushes (`--force`) and branch deletions on `main` are **blocked**.
- **AI agents MUST NOT locally merge into `main` or auto-merge Pull Requests.**
- Every change MUST be pushed to a dedicated non-`main` branch and submitted as a **Pull Request (PR) to `main`** for the repository owner to review and merge.

---

## 2. Harness-Specific Compliance Matrix

| Harness / IDE | Typical Models | Mandatory Git Behavior | Prohibited Actions |
|---|---|---|---|
| **ZCode** | `GLM 5.3` | Create `feat/*`, `fix/*`, `docs/*`, `chore/*` branch from `origin/main`; commit & push to that branch; open PR to `main` | `git push origin main`, `git merge ... main`, auto-merging PRs |
| **Antigravity** | `Gemini` (all tiers) | Same branch-first workflow + subagent worktree isolation; push feature branch only; open PR to `main` and stop | Pushing directly to `main`, merging PRs without owner sign-off |
| **Claude Code / Codex / Cursor / Other** | `Claude`, `GPT`, `o-series`, etc. | Branch from `origin/main`, run pre-PR gates, push feature branch, open PR to `main` | Direct `main` commits, bypassing `Protect main`, force-pushing |

---

## 3. Step-by-Step Pre-PR Workflow

Run these steps in order before writing code or opening a PR:

### Step 1 — Sync and Create a Feature Branch (Before Editing)
```bash
git fetch origin
git checkout -b feat/<short-descriptive-slug> origin/main
```
Use clear branch prefixes:
- `feat/<slug>` — new features or UI/API additions
- `fix/<slug>` — bug fixes
- `docs/<slug>` — documentation, PRD, README, or runbook updates
- `chore/<slug>` — CI/CD, Docker, GCP infra, or dependency hygiene
- `refactor/<slug>` — code cleanup without behavior change

### Step 2 — Respect Repository Guardrails While Implementing
- Keep `origin` pointed strictly at `https://github.com/naughtynova69/LedgerLens-project`. Never add or push to `Avani376/Ledgerlens`.
- Preserve the **Neuro-Symbolic Invariant**: `backend/app/detect/` must remain pure Python `stdlib` with **zero** LLM, network, or DB imports.
- Keep `sample_data/` deterministic: **6 findings** (`₹40,531.60` nominal sum) and **0 false positives** on the 4 clean controls (`INV-9001`, `INV-9010`, `INV-9400`, `INV-9500`).

### Step 3 — Run Mandatory Pre-PR Verification Gates
Before pushing your branch or opening a PR, run and verify:

```powershell
# 1. Backend unit & integration tests
backend\.venv\Scripts\pytest.exe -c backend\pytest.ini backend\tests -q

# 2. Frontend production build
npm --prefix frontend run build
```
*(On Linux/macOS, use `backend/.venv/bin/pytest -c backend/pytest.ini backend/tests -q`.)*

### Step 4 — Commit & Push to Your Feature Branch (Never `main`)
```bash
git status
git add <specific-files>
git commit -m "<type>(<scope>): <concise summary>"
git push -u origin <type>/<short-descriptive-slug>
```

### Step 5 — Open a Pull Request to `main` and Hand Off
- Open a PR targeting `base: main` from `head: <type>/<short-descriptive-slug>` (via `gh pr create` or the GitHub PR link printed by `git push`).
- Include in the PR description:
  - Summary of changes and modified file paths
  - Exact `pytest` and `npm run build` output observed after your final edit
  - Any GCP, schema, or environment variable impact
- **Stop after opening the PR** and report the PR URL to the user so the repository owner can review and merge it into `main`.

---

## 4. Multi-Agent & Subagent Rules
- Orchestrators spawning subagents/worktrees must assign each worker its own isolated branch/worktree and non-overlapping file paths.
- Subagents must **never** push to `main`, merge into `main`, or merge PRs.
- Only after consolidating verified worker commits onto a single integration feature branch may the orchestrator push that feature branch and open **one clean PR to `main`**.
