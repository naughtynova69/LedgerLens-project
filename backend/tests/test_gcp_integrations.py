"""Offline-safe integration and structural tests for LedgerLens GCP adapters and schemas."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
import types

from fastapi.testclient import TestClient
import pytest

from app import config
from app.gcp import (
    check_alloydb_connection,
    get_gcp_readiness_status,
    init_alloydb_schema,
    publish_recovery_event,
    resolve_secret,
    store_evidence_object,
)
from app.main import app

_GCP_ENV_VARS = (
    "GCP_PROJECT_ID",
    "GCP_LOCATION",
    "DB_BACKEND",
    "ALLOYDB_INSTANCE_URI",
    "ALLOYDB_USER",
    "ALLOYDB_PASS",
    "ALLOYDB_DB",
    "DATABASE_URL",
    "BQ_DATASET",
    "GCS_UPLOAD_BUCKET",
    "USE_VERTEX_AI",
    "PUBSUB_RECOVERY_TOPIC",
    "SECRET_MANAGER_PROJECT",
    "USE_SECRET_MANAGER",
)

_EXPECTED_POSTGRES_TABLES = {
    "vendors",
    "contracts",
    "purchase_orders",
    "goods_receipts",
    "invoices",
    "payments",
    "batches",
    "findings",
    "decisions",
    "audit_log",
    "policy_settings",
    "approvers",
    "credit_notes",
}


@pytest.fixture(autouse=True)
def clear_gcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear GCP env vars so tests run deterministically offline regardless of host .env."""
    for var_name in _GCP_ENV_VARS:
        monkeypatch.delenv(var_name, raising=False)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Return an isolated FastAPI TestClient backed by a temporary SQLite database."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test_gcp.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    with TestClient(app) as test_client:
        yield test_client


def _stub_google_cloud_module(
    monkeypatch: pytest.MonkeyPatch,
    submod_name: str,
    fake_mod: types.ModuleType,
) -> None:
    """Safely stub google.cloud.<submod_name> in sys.modules without breaking real packages."""
    try:
        import google  # type: ignore[import-not-found]
    except ImportError:
        google = types.ModuleType("google")
        google.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "google", google)

    try:
        import google.cloud  # type: ignore[import-not-found]
    except ImportError:
        google_cloud = types.ModuleType("google.cloud")
        google_cloud.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "google.cloud", google_cloud)
        monkeypatch.setattr(google, "cloud", google_cloud, raising=False)
    else:
        google_cloud = google.cloud

    monkeypatch.setitem(sys.modules, f"google.cloud.{submod_name}", fake_mod)
    monkeypatch.setattr(google_cloud, submod_name, fake_mod, raising=False)


def test_gcp_status_endpoint_offline(client: TestClient) -> None:
    resp = client.get("/api/gcp/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == ""
    assert data["location"] == "asia-south1"
    assert data["billing_ready"] is False

    expected_services = {
        "alloydb",
        "bigquery",
        "cloud_storage",
        "vertex_ai",
        "secret_manager",
        "pubsub",
    }
    assert set(data["services"].keys()) == expected_services

    for svc_name in expected_services:
        svc = data["services"][svc_name]
        assert svc["mode"] == "local_fallback"
        assert isinstance(svc["sdk_installed"], bool)
        assert isinstance(svc["target"], str) and svc["target"]

    alloydb_conn = data["alloydb_connection"]
    assert alloydb_conn["configured"] is False
    assert alloydb_conn["mode"] == "sqlite_fallback"
    assert alloydb_conn["connected"] is False


def test_gcp_readiness_configured_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-ledgerlens-proj")
    monkeypatch.setenv("GCP_LOCATION", "us-central1")
    monkeypatch.setenv("DB_BACKEND", "alloydb")
    monkeypatch.setenv(
        "ALLOYDB_INSTANCE_URI",
        "projects/demo-ledgerlens-proj/locations/us-central1/clusters/c/instances/i",
    )
    monkeypatch.setenv("BQ_DATASET", "custom_analytics")
    monkeypatch.setenv("GCS_UPLOAD_BUCKET", "ledgerlens-evidence-bucket")
    monkeypatch.setenv("USE_VERTEX_AI", "true")
    monkeypatch.setenv("SECRET_MANAGER_PROJECT", "demo-ledgerlens-proj")
    monkeypatch.setenv("PUBSUB_RECOVERY_TOPIC", "ledgerlens-recovery-events")

    status = get_gcp_readiness_status()
    assert status["project_id"] == "demo-ledgerlens-proj"
    assert status["location"] == "us-central1"
    assert status["billing_ready"] is True

    for svc_name in (
        "alloydb",
        "bigquery",
        "cloud_storage",
        "vertex_ai",
        "secret_manager",
        "pubsub",
    ):
        assert status["services"][svc_name]["mode"] == "configured"


def test_bigquery_sync_after_sample_seed_offline(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/sample_data")
    assert seed_resp.status_code == 200
    assert seed_resp.json()["findings_created"] == 6

    sync_resp = client.post("/api/gcp/bigquery/sync")
    assert sync_resp.status_code == 200
    data = sync_resp.json()

    assert data["mode"] == "local_simulation"
    assert data["synced"] is False
    assert data["dataset"] == "ledgerlens_analytics"
    assert data["tables"]["audited_invoices"] == 16
    assert data["tables"]["audit_findings"] == 6
    assert data["tables"]["audit_log_events"] >= 2
    assert data["total_rows_prepared"] == (
        data["tables"]["audited_invoices"]
        + data["tables"]["audit_findings"]
        + data["tables"]["audit_log_events"]
    )


def test_executive_analytics_after_sample_seed(client: TestClient) -> None:
    seed_resp = client.post("/api/seed/sample_data")
    assert seed_resp.status_code == 200
    seed_data = seed_resp.json()

    resp = client.get("/api/analytics/executive")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_audited_spend_inr"] > 0
    assert data["total_at_risk_inr"] > 0
    assert data["total_at_risk_inr"] >= seed_data["total_at_risk"]
    assert data["open_at_risk_inr"] == data["total_at_risk_inr"]
    assert data["recovered_inr"] == 0.0
    assert data["recovery_rate_pct"] == 0.0
    assert data["total_findings"] == 6

    expected_leakage = round(
        (data["total_at_risk_inr"] / data["total_audited_spend_inr"]) * 100.0, 2
    )
    assert data["leakage_pct_of_spend"] > 0
    assert data["leakage_pct_of_spend"] == pytest.approx(expected_leakage, abs=0.01)

    assert data["fx_rates"]["INR"] == 1.0
    assert data["fx_rates"]["USD"] == 88.0
    assert data["fx_rates"]["EUR"] == 95.0
    assert data["fx_rates"]["GBP"] == 112.0

    top_vendors = data["top_vendors"]
    assert isinstance(top_vendors, list)
    assert len(top_vendors) >= 1
    for item in top_vendors:
        assert {
            "vendor_id",
            "vendor_name",
            "finding_count",
            "amount_at_risk_inr",
            "open_inr",
            "recovered_inr",
        }.issubset(item.keys())
        assert item["finding_count"] >= 1
        assert item["amount_at_risk_inr"] > 0

    sort_keys = [(-v["amount_at_risk_inr"], v["vendor_id"]) for v in top_vendors]
    assert sort_keys == sorted(sort_keys)

    assert set(data["by_rule"].keys()) >= {"R1", "R2", "R3", "R4", "R5"}
    assert sum(bucket["count"] for bucket in data["by_rule"].values()) == 6

    # Verify a recovery decision updates recovered_inr and recovery_rate_pct
    findings_resp = client.get("/api/findings")
    assert findings_resp.status_code == 200
    first_id = findings_resp.json()[0]["finding_id"]

    dec_resp = client.post(
        f"/api/findings/{first_id}/decision",
        json={"action": "recovery", "reviewer": "cfo_audit", "note": "Claim issued."},
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["status"] == "recovery"

    updated = client.get("/api/analytics/executive").json()
    assert updated["recovered_inr"] > 0
    assert updated["recovery_rate_pct"] > 0
    assert updated["open_at_risk_inr"] < updated["total_at_risk_inr"]


def test_store_evidence_object_local_fallback_and_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"invoice_number,amount\nINV-1001,4956.00\n"
    temp_file = tmp_path / "evidence.csv"
    temp_file.write_bytes(payload)
    expected_digest = hashlib.sha256(payload).hexdigest()

    result = store_evidence_object(temp_file, "B-0001", "evidence.csv")
    assert result["backend"] == "local"
    assert result["uri"] == str(temp_file)
    assert result["bucket"] == ""
    assert result["size_bytes"] == len(payload)
    assert len(result["sha256"]) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", result["sha256"])
    assert result["sha256"] == expected_digest

    # Also verify graceful fallback to local when GCS bucket is set but client raises offline
    monkeypatch.setenv("GCS_UPLOAD_BUCKET", "offline-bucket")
    fake_storage = types.ModuleType("google.cloud.storage")

    def _failing_client():
        raise RuntimeError("offline storage client")

    fake_storage.Client = _failing_client  # type: ignore[attr-defined]
    _stub_google_cloud_module(monkeypatch, "storage", fake_storage)

    fallback_res = store_evidence_object(temp_file, "B-0002", "evidence.csv")
    assert fallback_res["backend"] == "local"
    assert fallback_res["uri"] == str(temp_file)
    assert fallback_res["sha256"] == expected_digest


def test_resolve_secret_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERLENS_TEST_SECRET", "env-secret-value")
    assert (
        resolve_secret("gemini-api-key", "LEDGERLENS_TEST_SECRET", default="fallback")
        == "env-secret-value"
    )

    monkeypatch.delenv("LEDGERLENS_TEST_SECRET", raising=False)
    assert (
        resolve_secret("gemini-api-key", "LEDGERLENS_TEST_SECRET", default="fallback")
        == "fallback"
    )
    assert resolve_secret("gemini-api-key", "LEDGERLENS_TEST_SECRET") == ""


def test_publish_recovery_event_offline_local_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = publish_recovery_event(
        "finding.decision", {"finding_id": "F-0001", "status": "recovery"}
    )
    assert res == {
        "published": False,
        "mode": "local_noop",
        "topic": "",
        "event_type": "finding.decision",
    }

    # Verify graceful local_noop fallback when topic is set but Pub/Sub client fails offline
    monkeypatch.setenv("PUBSUB_RECOVERY_TOPIC", "recovery-topic")
    fake_pubsub = types.ModuleType("google.cloud.pubsub_v1")

    def _failing_publisher():
        raise RuntimeError("offline pubsub client")

    fake_pubsub.PublisherClient = _failing_publisher  # type: ignore[attr-defined]
    _stub_google_cloud_module(monkeypatch, "pubsub_v1", fake_pubsub)

    fallback_res = publish_recovery_event(
        "finding.decision", {"finding_id": "F-0002", "status": "rejected"}
    )
    assert fallback_res == {
        "published": False,
        "mode": "local_noop",
        "topic": "recovery-topic",
        "event_type": "finding.decision",
    }


def test_check_alloydb_connection_offline_sqlite_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = check_alloydb_connection()
    assert res["configured"] is False
    assert res["mode"] == "sqlite_fallback"
    assert res["connected"] is False

    schema_res = init_alloydb_schema()
    assert schema_res == {"applied": False, "mode": "sqlite_fallback"}

    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/ledgerlens")
    explicit_sqlite = check_alloydb_connection()
    assert explicit_sqlite["configured"] is False
    assert explicit_sqlite["mode"] == "sqlite_fallback"
    assert explicit_sqlite["connected"] is False


def test_schema_postgres_defines_all_tables() -> None:
    schema_path = Path(__file__).resolve().parent.parent / "schema_postgres.sql"
    assert schema_path.is_file()
    sql_text = schema_path.read_text(encoding="utf-8")

    tables = re.findall(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        sql_text,
        flags=re.IGNORECASE,
    )
    assert len(tables) == 13
    assert set(tables) == _EXPECTED_POSTGRES_TABLES


def test_bigquery_schema_defines_tables_and_views() -> None:
    bq_schema_path = (
        Path(__file__).resolve().parent.parent.parent / "infra" / "bigquery" / "schema.sql"
    )
    assert bq_schema_path.is_file()
    sql_text = bq_schema_path.read_text(encoding="utf-8")

    tables = re.findall(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)",
        sql_text,
        flags=re.IGNORECASE,
    )
    views = re.findall(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)",
        sql_text,
        flags=re.IGNORECASE,
    )

    assert {"audited_invoices", "audit_findings", "audit_log_events"}.issubset(
        set(tables)
    )
    assert "v_vendor_leakage_ranking" in views
    assert {
        "v_vendor_leakage_ranking",
        "v_rule_exposure_summary",
        "v_recovery_roi",
    }.issubset(set(views))
