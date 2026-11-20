# Contributing to LedgerLens

Read this once before your first commit. It is short on purpose.

## 0. Golden rules

1. **Never commit secrets.** `.env` stays local. `backend/.env.example` is the only env file in git.
2. **Never commit `Context_File/` or `Content/`.** They are git-ignored on purpose — the context pack is shared manually by the team lead.
3. **Deterministic rules decide; Gemini extracts and explains.** Never let the LLM be the only source of a finding.
4. Every finding must carry **evidence** (record IDs + field values) and a **confidence**. No exceptions.
5. Blocked for more than 30 minutes? Post in the team chat. Do not silently rewrite someone else's module.

## 1. Setup

Follow the Quickstart in `README.md`. Verify before you start coding:

```bash
cd backend
python -m pytest -q          # tests pass
uvicorn app.main:app --reload # /health returns {"status": "ok", ...}
```

## 2. Branches

One branch per task, named after the workstream:

| Pattern | Example |
|---------|---------|
| `feature/<area>-<thing>` | `feature/detect-rule-r1`, `feature/dashboard-finding-card` |
| `fix/<area>-<thing>` | `fix/normalize-vendor-accents` |
| `docs/<topic>` | `docs/api-spec-update` |

`main` must always work: if `pytest` fails on your branch, do not merge.

## 3. Commits

Use conventional-commit prefixes so history stays readable:

```
feat: add R1 duplicate-invoice detector
fix: normalize vendor names with trailing punctuation
docs: add R2 thresholds to detection rules spec
chore: pin fastapi version
```

Small, focused commits. A commit that says "various changes" is a smell.

## 4. Pull requests

- One PR per task. Title = the task.
- Checklist before requesting review:
  - [ ] `python -m pytest -q` passes locally
  - [ ] No `.env`, no secrets, no `Context_File/` files in the diff
  - [ ] New rule? It is deterministic, documented in `docs/04_DETECTION_RULES.md`, and has a unit test
  - [ ] New endpoint? It is documented in `docs/05_API_SPEC.md`
- One approval is enough for MVP pace. Review within 30 minutes when someone asks.

## 5. Code style

- Python: follow PEP 8; type hints on public functions; docstrings on every rule module (each rule must explain *why it fires* in one paragraph — that text feeds the explanation generator).
- Keep detection rules **pure** (no DB, no network, no Gemini imports) so they stay unit-testable.
- Frontend: function components + hooks; keep API calls in one `api.js` module.

## 6. Where things live

| Question | Answer |
|----------|--------|
| What are we building? | `docs/01_PRODUCT_SPEC.md` |
| How do modules fit? | `docs/02_ARCHITECTURE.md` |
| What do the data tables look like? | `docs/03_DATA_MODEL.md` |
| How does each detection rule work? | `docs/04_DETECTION_RULES.md` |
| What endpoints exist? | `docs/05_API_SPEC.md` |
| How do we use Gemini? | `docs/06_GEMINI_INTEGRATION.md` |
| Who does what, by when? | `docs/07_BUILD_PLAN.md` |

Deeper offline context (idea history, judge Q&A, full prompts) lives in the manually-shared context pack — ask the team lead.
