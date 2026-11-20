"""Unit tests for Workspaces/RBAC (Track #9) and Webhook/CFO Copilot (Track #11)."""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.copilot import COPILOT_MODEL, ask_copilot, dispatch_webhook_alert
from app.db import init_schema
from app.workspaces import (
    create_workspace,
    ensure_workspaces_table,
    list_workspaces,
    require_role,
)


# ---------------------------------------------------------------------------
# Track #9: Multi-tenant Workspaces & RBAC
# ---------------------------------------------------------------------------


def test_workspaces_seed_and_create() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        ensure_workspaces_table(conn)
        initial = list_workspaces(conn)
        assert len(initial) == 1
        assert initial[0]["workspace_id"] == "default"

        created = create_workspace(conn, "Acme Audit LLP", client_code="acme01")
        assert created["name"] == "Acme Audit LLP"
        assert created["client_code"] == "ACME01"
        assert created["workspace_id"].startswith("acme-audit-llp-")

        all_ws = list_workspaces(conn)
        assert len(all_ws) == 2
        assert {w["workspace_id"] for w in all_ws} == {"default", created["workspace_id"]}

        with pytest.raises(ValueError):
            create_workspace(conn, "   ")
    finally:
        conn.close()


def test_require_role_rbac() -> None:
    assert require_role("analyst", ["analyst", "admin"]) == "analyst"
    assert require_role(" Controller ", ["controller", "auditor"]) == "controller"
    assert require_role("AUDITOR", ["auditor"]) == "auditor"
    assert require_role("admin", ["admin"]) == "admin"

    with pytest.raises(PermissionError):
        require_role("analyst", ["controller", "admin"])

    with pytest.raises(PermissionError):
        require_role("superuser", ["admin"])


# ---------------------------------------------------------------------------
# Track #11: Webhook Dispatcher & Grounded CFO Copilot
# ---------------------------------------------------------------------------


def test_dispatch_webhook_alert_noop_and_success() -> None:
    assert dispatch_webhook_alert("", "finding.high", {"id": "F-1"}) == {
        "sent": False,
        "status_code": None,
        "error": None,
    }
    assert dispatch_webhook_alert(None, "finding.high", {"id": "F-1"}) == {
        "sent": False,
        "status_code": None,
        "error": None,
    }

    class _FakeResp:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    captured_req = {}

    def _fake_urlopen(req, timeout=3.0):
        captured_req["url"] = req.full_url
        captured_req["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp()

    with patch("app.copilot.guarded_urlopen", side_effect=_fake_urlopen):
        res = dispatch_webhook_alert(
            "https://hooks.example.com/alert",
            "finding.created",
            {"finding_id": "F-100", "amount_at_risk": 45000.0},
        )

    assert res == {"sent": True, "status_code": 202, "error": None}
    assert captured_req["url"] == "https://hooks.example.com/alert"
    assert captured_req["body"]["event_type"] == "finding.created"
    assert captured_req["body"]["payload"]["finding_id"] == "F-100"


def test_dispatch_webhook_alert_handles_http_error() -> None:
    err = urllib.error.HTTPError(
        url="https://hooks.example.com/alert",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )
    with patch("app.copilot.guarded_urlopen", side_effect=err):
        res = dispatch_webhook_alert("https://hooks.example.com/alert", "test", {})
    assert res["sent"] is False
    assert res["status_code"] == 500
    assert res["error"] is not None


def test_ask_copilot_offline_fallback_cites_grounded_proof_trail() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        proof = {"math": {"billed_rate": 120.0, "contract_rate": 100.0, "qty": 10}}
        conn.execute(
            "INSERT INTO findings "
            "(finding_id, rule_id, title, severity, amount_at_risk, currency, status, proof_trail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "F-901",
                "R2",
                "Contract rate variance",
                "high",
                200.0,
                "INR",
                "open",
                json.dumps(proof),
            ),
        )
        conn.commit()

        with patch("app.copilot.has_live_ai_credentials", return_value=False):
            result = ask_copilot(conn, "What is our top risk?", workspace_id="acme")

        assert result["mode"] == "deterministic_fallback"
        assert result["model"] is None
        assert result["workspace_id"] == "acme"
        assert result["stats"]["total_findings"] == 1
        assert result["stats"]["total_amount_at_risk"] == 200.0
        assert "F-901" in result["answer"]
        assert "R2" in result["answer"]
        assert "200.00" in result["answer"]
        assert "120.0" in result["answer"]
    finally:
        conn.close()


def test_ask_copilot_live_gemini_and_empty_db() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        # Empty DB without findings table should not crash
        with patch("app.copilot.has_live_ai_credentials", return_value=False):
            empty_res = ask_copilot(conn, "Any risks?")
        assert empty_res["mode"] == "deterministic_fallback"
        assert empty_res["stats"]["total_findings"] == 0

        # Live Gemini path
        init_schema(conn)
        called_models: list[str] = []

        class _FakeModels:
            def generate_content(self, model, contents):
                called_models.append(model)
                return SimpleNamespace(text="Top risk is F-901 (R2) with 200.0 INR.")

        fake_client = SimpleNamespace(models=_FakeModels())
        with (
            patch("app.copilot.has_live_ai_credentials", return_value=True),
            patch("app.copilot.create_genai_client", return_value=fake_client),
        ):
            live_res = ask_copilot(conn, "Summarize exposure", workspace_id="default")

        assert called_models == [COPILOT_MODEL]
        assert live_res["mode"] == "gemini"
        assert live_res["model"] == "gemini-3.8-vision-flash"
        assert "F-901" in live_res["answer"]
    finally:
        conn.close()
