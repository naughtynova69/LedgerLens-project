"""Upload helpers used by app.main (kept framework-free for testability)."""
from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

from .. import config

VALID_KINDS = {"invoices", "purchase_orders", "contracts", "payments", "payment_ledger"}

# CSV column expectations per kind — must match docs/03_DATA_MODEL.md.
REQUIRED_COLUMNS = {
    "invoices": {"invoice_number", "vendor_id", "invoice_date", "item",
                 "quantity", "unit_price", "currency", "tax_pct", "line_total"},
    "purchase_orders": {"po_id", "vendor_id", "item", "quantity", "unit_price", "currency"},
    "contracts": {"contract_id", "vendor_id", "item", "contracted_unit_price"},
    "payments": {"payment_id", "invoice_number", "amount", "currency"},
}
# A raw bank/payment ledger export uses the same minimal shape as payments.
REQUIRED_COLUMNS["payment_ledger"] = REQUIRED_COLUMNS["payments"]


def validate_csv(path: Path, kind: str) -> list[str]:
    """Return a list of problems (empty = valid). Fails closed on bad headers."""
    if kind not in REQUIRED_COLUMNS:
        return [f"unknown kind: {kind}"]
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = {h.strip().lower() for h in next(reader)}
        except StopIteration:
            return ["empty CSV file"]
    required = REQUIRED_COLUMNS[kind]
    missing = sorted(required - header)
    return [f"missing required columns: {', '.join(missing)}"] if missing else []


def save_stream_to_upload(fileobj, original_name: str, batch_id: str) -> Path:
    """Persist an upload under UPLOAD_DIR with its batch id as provenance."""
    upload_dir = Path(config.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{batch_id}-{Path(original_name or 'upload').name}"
    fileobj.seek(0)
    with dest.open("wb") as out:
        shutil.copyfileobj(fileobj, out)
    return dest


def parse_csv_bytes(data: bytes) -> list[dict]:
    """CSV bytes -> dict rows (used by the extract stage for CSV batches)."""
    reader = csv.DictReader(io.StringIO(data.decode("utf-8", errors="replace")))
    return [dict(row) for row in reader]
