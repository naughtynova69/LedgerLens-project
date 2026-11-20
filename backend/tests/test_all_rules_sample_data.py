"""Acceptance test: all 6 planted anomalies detected and zero false positives on controls."""
from __future__ import annotations

import csv
from pathlib import Path
import pytest

from app.db import get_connection, init_schema
from app.services import run_detection


@pytest.fixture()
def sample_conn():
    conn = get_connection(":memory:")
    init_schema(conn)

    sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_data"
    for table in ["vendors", "contracts", "purchase_orders", "invoices", "payments"]:
        p = sample_dir / f"{table}.csv"
        with p.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cols = list(row.keys())
                placeholders = ",".join(["?"] * len(cols))
                conn.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                    list(row.values()),
                )

    conn.commit()
    yield conn
    conn.close()


def test_detects_all_six_sample_anomalies(sample_conn):
    res = run_detection(sample_conn)
    assert res["findings_created"] == 6

    findings = sample_conn.execute(
        "SELECT finding_id, rule_id, title, severity, amount_at_risk, currency FROM findings"
    ).fetchall()
    by_rule = {}
    for f in findings:
        by_rule.setdefault(f["rule_id"], []).append(f)

    # R1: duplicate
    assert len(by_rule["R1"]) == 1
    assert by_rule["R1"][0]["amount_at_risk"] == 4956.0
    assert by_rule["R1"][0]["severity"] == "critical"

    # R2: contract price leakage
    assert len(by_rule["R2"]) == 1
    assert by_rule["R2"][0]["amount_at_risk"] == 318.6
    assert by_rule["R2"][0]["severity"] == "high"

    # R3: PO overbilling
    assert len(by_rule["R3"]) == 1
    assert by_rule["R3"][0]["amount_at_risk"] == 2832.0
    assert by_rule["R3"][0]["severity"] == "high"

    # R4: currency mismatch + tax error
    assert len(by_rule["R4"]) == 2
    amounts = sorted([f["amount_at_risk"] for f in by_rule["R4"]])
    assert amounts == [225.0, 2700.0]

    # R5: cancelled service
    assert len(by_rule["R5"]) == 1
    assert by_rule["R5"][0]["amount_at_risk"] == 29500.0
    assert by_rule["R5"][0]["severity"] == "critical"

    total_at_risk = sum(f["amount_at_risk"] for f in findings)
    assert total_at_risk == pytest.approx(40531.60, 0.01)
