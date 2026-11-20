# LedgerLens Backend

FastAPI service: ingestion → Gemini extraction → normalization → deterministic detection → explanation → workflow.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # add your GEMINI_API_KEY
uvicorn app.main:app --reload
```

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>

## Test

```bash
python -m pytest -q
```

Detection rules and the service layer are pure stdlib — the full test suite runs **without** installing any dependencies.

## Layout

| Path | Responsibility |
|------|----------------|
| `app/main.py` | FastAPI routes (see `docs/05_API_SPEC.md`) |
| `app/config.py` | Env config — reads `.env`, never contains secrets |
| `app/db.py` + `schema.sql` | SQLite schema & connection helpers |
| `app/services.py` | Service layer between routes and the deterministic core |
| `app/ingest/` | Upload storage & batch creation |
| `app/extract/` | **Gemini** — PDF/scan → structured JSON (`gemini_extract.py`, schemas in `schemas.py`) |
| `app/normalize/` | Deterministic cleanup: vendor names, currency, amounts |
| `app/detect/` | **The explainable core.** R1–R5 as pure functions. NO DB/network/Gemini imports here. |
| `app/explain/` | **Gemini** — rule output → CFO-ready explanation |
| `tests/` | Unit tests for rules, services, normalization |

## Where the work is (search `TODO`)

| Owner | Task | File |
|-------|------|------|
| C | Implement R2–R5 (R1 is the reference implementation) | `app/detect/rules/*.py` |
| B | Extraction + explanation are written — test against real PDFs & tune prompts | `app/extract/`, `app/explain/` |
| A | Wire upload → extract → detect orchestration per `docs/07_BUILD_PLAN.md` | `app/main.py` |

**Principle:** Gemini extracts and explains; the rules engine decides. Detection findings must be reproducible without the LLM.
