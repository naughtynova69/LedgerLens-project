"""Tests for CSV upload validation (ingest stage)."""
from app.ingest.router import validate_csv


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


VALID_INVOICE_CSV = (
    "invoice_number,vendor_id,invoice_date,po_id,line_no,item,quantity,"
    "unit_price,currency,tax_pct,line_total,status\n"
    "INV-1,V001,2026-10-14,PO-1001,1,Widget,1,10.0,INR,18,11.80,unpaid\n"
)


def test_valid_invoice_csv_has_no_problems(tmp_path):
    path = _write(tmp_path, "ok.csv", VALID_INVOICE_CSV)
    assert validate_csv(path, "invoices") == []


def test_missing_columns_are_reported(tmp_path):
    path = _write(tmp_path, "bad.csv", "foo,bar\n1,2\n")
    problems = validate_csv(path, "invoices")
    assert problems and "missing required columns" in problems[0]


def test_payment_ledger_uses_payments_columns(tmp_path):
    path = _write(tmp_path, "pay.csv",
                  "payment_id,invoice_number,amount,currency\n")
    assert validate_csv(path, "payment_ledger") == []


def test_empty_csv_is_reported(tmp_path):
    path = _write(tmp_path, "empty.csv", "")
    assert validate_csv(path, "invoices") == ["empty CSV file"]
