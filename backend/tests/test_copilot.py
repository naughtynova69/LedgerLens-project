"""Comprehensive unit tests for CFO Copilot (backend/app/copilot.py)."""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.copilot import DEFAULT_HMS_MODEL, ask_copilot
from app.db import init_schema
from app.workspaces import create_workspace, ensure_workspaces_table


def _seed_finding(
    conn: sqlite3.Connection,
    *,
    finding_id: str,
    rule_id: str,
    title: str,
    severity: str,
    amount_at_risk: float,
    status: str = "open",
    workspace_id: str = "default",
    proof_trail: dict | str | None = None,
    recommended_action: str = "Hold payment and verify",
) -> None:
    conn.execute(
        "INSERT INTO findings "
        "(finding_id, rule_id, title, severity, amount_at_risk, currency, status, "
        "recommended_action, proof_trail, workspace_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            finding_id,
            rule_id,
            title,
            severity,
            amount_at_risk,
            "INR",
            status,
            recommended_action,
            json.dumps(proof_trail) if isinstance(proof_trail, dict) else (proof_trail or "{}"),
            workspace_id,
        ),
    )


def test_copilot_citations_proof_trail_is_string_and_workspace_isolated() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        ensure_workspaces_table(conn)
        ws_alpha = create_workspace(conn, "Alpha Corp", client_code="ALPHA")["workspace_id"]
        ws_empty = create_workspace(conn, "Empty Corp", client_code="EMPTY")["workspace_id"]

        _seed_finding(
            conn,
            finding_id="F-DEF-1",
            rule_id="R2",
            title="Default workspace variance",
            severity="high",
            amount_at_risk=9000.0,
            workspace_id="default",
            proof_trail={"billed": 190, "contract": 100},
        )
        _seed_finding(
            conn,
            finding_id="F-ALP-1",
            rule_id="R1",
            title="Alpha duplicate invoice",
            severity="critical",
            amount_at_risk=2500.0,
            workspace_id=ws_alpha,
            proof_trail={"duplicate_of": "INV-100"},
        )
        conn.commit()

        with (
            patch("app.copilot.has_live_ai_credentials", return_value=False),
            patch("app.copilot._resolve_openai_config", return_value=None),
        ):
            alpha_res = ask_copilot(conn, "What is our risk?", workspace_id=ws_alpha)
            empty_res = ask_copilot(conn, "What is our risk?", workspace_id=ws_empty)

        assert alpha_res["mode"] == "deterministic_fallback"
        assert alpha_res["stats"]["total_findings"] == 1
        assert alpha_res["stats"]["total_amount_at_risk"] == 2500.0
        assert "F-ALP-1" in alpha_res["answer"]
        assert "F-DEF-1" not in alpha_res["answer"]
        assert len(alpha_res["citations"]) == 1
        assert isinstance(alpha_res["citations"][0]["proof_trail"], str)
        assert "INV-100" in alpha_res["citations"][0]["proof_trail"]

        assert empty_res["mode"] == "deterministic_fallback"
        assert empty_res["stats"]["total_findings"] == 0
        assert empty_res["citations"] == []
    finally:
        conn.close()


def test_copilot_context_parameters_and_question_prioritization() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        _seed_finding(
            conn,
            finding_id="F-R2-BIG",
            rule_id="R2",
            title="Large contract variance",
            severity="medium",
            amount_at_risk=5000.0,
            proof_trail={"variance": 5000},
        )
        _seed_finding(
            conn,
            finding_id="F-R1-DUP",
            rule_id="R1",
            title="Duplicate vendor bill",
            severity="high",
            amount_at_risk=1200.0,
            proof_trail={"invoice": "INV-77"},
        )
        conn.commit()

        with (
            patch("app.copilot.has_live_ai_credentials", return_value=False),
            patch("app.copilot._resolve_openai_config", return_value=None),
        ):
            res = ask_copilot(
                conn,
                "Show me duplicate invoices",
                workspace_id="default",
                current_page="exceptions",
                selected_finding_id="F-R1-DUP",
                conversation_history=[{"role": "user", "content": "Hi"}],
            )

        assert res["mode"] == "deterministic_fallback"
        assert "Context page: exceptions." in res["answer"]
        assert "Focused finding: F-R1-DUP." in res["answer"]
        assert "Exposure by rule:" in res["answer"]
        # Focused/duplicate finding should appear before the higher-amount R2 finding
        assert res["answer"].index("F-R1-DUP") < res["answer"].index("F-R2-BIG")
    finally:
        conn.close()


def test_copilot_gemini_failure_falls_back_to_openai_reasoning_content(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        _seed_finding(
            conn,
            finding_id="F-10",
            rule_id="R3",
            title="PO quantity mismatch",
            severity="high",
            amount_at_risk=750.0,
            proof_trail={"po_qty": 5, "billed_qty": 8},
        )
        conn.commit()

        monkeypatch.setenv("HMS_API_KEY", "hms-test-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("COPILOT_OPENAI_API_KEY", raising=False)

        class _FakeResp:
            def __init__(self, payload: dict):
                self._data = json.dumps(payload).encode("utf-8")

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        captured_headers: dict[str, str] = {}

        def _fake_urlopen(req, timeout=10.0):
            captured_headers.update({k.lower(): v for k, v in req.header_items()})
            return _FakeResp(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "reasoning_content": "F-10 (R3) has 750.00 INR at risk.",
                            }
                        }
                    ]
                }
            )

        class _BrokenModels:
            def generate_content(self, model, contents):
                raise TimeoutError("Gemini timed out")

        with (
            patch("app.copilot.has_live_ai_credentials", return_value=True),
            patch("app.copilot.create_genai_client", return_value=SimpleNamespace(models=_BrokenModels())),
            patch("app.copilot.guarded_urlopen", side_effect=_fake_urlopen),
        ):
            res = ask_copilot(conn, "Explain F-10", workspace_id="default")

        assert res["mode"] == "openai_compatible"
        assert res["model"] == DEFAULT_HMS_MODEL
        assert "F-10" in res["answer"]
        assert "user-agent" in captured_headers
        assert "LedgerLens-Copilot" in captured_headers["user-agent"]
    finally:
        conn.close()


def test_copilot_openai_timeout_and_empty_content_fall_back_deterministically(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        _seed_finding(
            conn,
            finding_id="F-22",
            rule_id="R4",
            title="GST rate mismatch",
            severity="medium",
            amount_at_risk=420.0,
            proof_trail={"expected_tax": 18, "billed_tax": 28},
        )
        conn.commit()

        monkeypatch.setenv("HMS_API_KEY", "hms-test-key")

        with (
            patch("app.copilot.has_live_ai_credentials", return_value=False),
            patch("app.copilot.guarded_urlopen", side_effect=urllib.error.URLError("timed out")),
        ):
            timeout_res = ask_copilot(conn, "Any tax issues?", workspace_id="default")

        assert timeout_res["mode"] == "deterministic_fallback"
        assert timeout_res["model"] is None
        assert "F-22" in timeout_res["answer"]
        assert "420.00" in timeout_res["answer"]
    finally:
        conn.close()
