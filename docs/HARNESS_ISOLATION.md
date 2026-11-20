# Multi-Harness Isolation Protocol (Antigravity + ZCode)

> **Goal:** Allow **Antigravity (Gemini)** and **ZCode (`GLM 5.3`)** to work simultaneously on `LedgerLens-project` with **zero race conditions, zero branch collisions, and zero overwritten files**.

---

## 1. Golden Rules
1. **Separate Git Worktrees:** Never run two harnesses in the same directory (`C:\LedgerLens\LedgerLens-project`). Each harness MUST operate in its own dedicated git worktree:
   - **Antigravity:** `C:\LedgerLens\wt-antigravity-<slug>` (or primary repo when ZCode is in a worktree)
   - **ZCode (`GLM 5.3`):** `C:\LedgerLens\wt-zcode-<slug>`
2. **Separate Feature Branches:** Each harness branches from `origin/main` with a harness-distinct `feat/`, `fix/`, `docs/`, or `chore/` branch.
3. **Non-Overlapping Path Ownership:** Before editing any file, each harness claims its owned paths in the shared lock registry (`<git-common-dir>/harness-locks.json`) via `scripts/harness_lock.py`. Overlapping claims fail immediately with exit code `2`.
4. **Shared Integration Files (`backend/app/main.py`, `backend/app/services.py`, `docs/CONTEXT_LOG.md`):** Only one harness claims a shared integration file at a time; the other waits or puts its changes in a dedicated module/file for PR-order merge.

---

## 2. Standard Workflow

### Step A — Check Active Locks
```powershell
python scripts/harness_lock.py status
```

### Step B — Create Isolated Worktree & Claim Ownership
**For ZCode (`GLM 5.3`):**
```powershell
git -C C:\LedgerLens\LedgerLens-project worktree add C:\LedgerLens\wt-zcode-vision-accuracy -b feat/vision-38-accuracy origin/main
python C:\LedgerLens\LedgerLens-project\scripts\harness_lock.py claim `
  --harness zcode `
  --branch feat/vision-38-accuracy `
  --worktree C:\LedgerLens\wt-zcode-vision-accuracy `
  --paths backend/app/extract backend/tests/test_extract.py backend/tests/eval_gemini_extraction.py
```

**For Antigravity (`Gemini`):**
```powershell
git -C C:\LedgerLens\LedgerLens-project worktree add C:\LedgerLens\wt-antigravity-roadmap -b feat/roadmap-next origin/main
python C:\LedgerLens\LedgerLens-project\scripts\harness_lock.py claim `
  --harness antigravity `
  --branch feat/roadmap-next `
  --worktree C:\LedgerLens\wt-antigravity-roadmap `
  --paths frontend/src backend/app/finance backend/app/detect
```

### Step C — Work, Verify, Push & Release
1. Edit **only** inside your claimed worktree and claimed paths.
2. Run pre-PR checks (`pytest` + `npm --prefix frontend run build`).
3. Append a short entry to `docs/CONTEXT_LOG.md` (or let the PR author update it at merge time to avoid merge conflicts), push your feature branch, and open a PR to `main`.
4. Release the lock and remove the temporary worktree after PR creation:
   ```powershell
   python C:\LedgerLens\LedgerLens-project\scripts\harness_lock.py release --harness zcode
   git -C C:\LedgerLens\LedgerLens-project worktree remove C:\LedgerLens\wt-zcode-vision-accuracy
   ```
