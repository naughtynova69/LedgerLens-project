"""Deterministic relational-to-graph projection (master-prompt §2.1 stage 5).

SQLite/AlloyDB remains the system of record. This module projects the
normalized relational tables into LadybugDB as typed NODE/REL tables:

- Vendor/Approver personal infrastructure (bank accounts, tax ids, addresses)
  becomes first-class nodes so cross-entity patterns become single shared nodes.
- Invoices fold their line rows into one Invoice node + InvoiceLine children.
- GOVERNED_BY links each invoice to the contracts of the same
  (vendor, item, date-window) so amendment lineage (AMENDS) is traversable.

Projection is a full deterministic rebuild (``MATCH (n) DETACH DELETE n`` then
re-insert), so running it twice produces exactly the same node/edge counts with
zero duplicates, and a Cloud Run cold start can reconstruct the whole graph
from the relational system of record in milliseconds.
"""
from __future__ import annotations

from datetime import date
import hashlib
import re
import sqlite3
import time
from typing import Any

from .client import GraphClient
from .schema import initialize_schema

_CLEAR_NODES = "MATCH (n) DETACH DELETE n"


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm_phone(raw: Any) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    return digits[-10:] if len(digits) >= 10 else digits


def _email_domain(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if "@" not in text:
        return ""
    return text.rsplit("@", 1)[-1].strip()


def _norm_bank_account(raw: Any) -> str:
    return re.sub(r"\s+", "", str(raw or "")).upper()


def _mask_account(normalized: str) -> str:
    return f"••••{normalized[-4:]}" if len(normalized) >= 4 else normalized


def _bank_code(normalized: str) -> str:
    return normalized[:4]


def _address_hash(raw: Any) -> str:
    normalized = _norm_text(raw).lower()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _address_parts(raw: Any) -> tuple[str, str]:
    """'12 MG Road, Bengaluru, IN' -> ('bengaluru', 'in'). Deterministic split."""
    tokens = [part.strip().lower() for part in _norm_text(raw).split(",") if part.strip()]
    if len(tokens) >= 2:
        return tokens[-2], tokens[-1]
    return "", ""


def _tax_meta(raw: Any) -> tuple[str, str]:
    """('GSTIN07AAACS1234A1Z5', ...) -> ('GSTIN', 'IN'); ('EIN-98-...', ...) -> ('EIN', 'US')."""
    text = str(raw or "").strip().upper()
    if not text:
        return "", ""
    if text.startswith("GSTIN"):
        return "GSTIN", "IN"
    if text.startswith("EIN"):
        return "EIN", "US"
    return "OTHER", ""


def _norm_item(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _in_window(invoice_date: str, effective: str, expiry: str) -> bool:
    try:
        day = date.fromisoformat(str(invoice_date or "")[:10])
    except ValueError:
        return False
    if effective and day < date.fromisoformat(str(effective)[:10]):
        return False
    if expiry and day > date.fromisoformat(str(expiry)[:10]):
        return False
    return True


def _fold_invoices(invoice_rows: list[dict]) -> dict[str, dict]:
    """Fold per-line invoice rows into one header record per invoice_number."""
    invoices: dict[str, dict] = {}
    for row in invoice_rows:
        number = str(row.get("invoice_number", ""))
        header = invoices.setdefault(number, {
            "invoice_id": number,
            "invoice_number": number,
            "vendor_id": str(row.get("vendor_id", "")),
            "invoice_date": str(row.get("invoice_date", "") or ""),
            "po_id": str(row.get("po_id") or "").strip(),
            "approver_id": str(row.get("approver_id") or "").strip(),
            "currency": str(row.get("currency", "INR")),
            "status": str(row.get("status", "unpaid")),
            "batch_id": str(row.get("source_file", "") or "upload"),
            "grand_total": 0.0,
            "lines": [],
        })
        header["grand_total"] += float(row.get("line_total") or 0.0)
        header["lines"].append({
            "line_id": f"{number}#{int(row.get('line_no') or 1)}",
            "item_key": _norm_item(row.get("item")),
            "description": str(row.get("item", "")),
            "quantity": float(row.get("quantity") or 0.0),
            "unit_price": float(row.get("unit_price") or 0.0),
            "line_total": float(row.get("line_total") or 0.0),
        })
    return invoices


def _bank_accounts_from_rows(rows: list[dict], bank_column: str) -> list[dict]:
    accounts: dict[str, dict] = {}
    for row in rows:
        normalized = _norm_bank_account(row.get(bank_column))
        if not normalized:
            continue
        accounts.setdefault(normalized, {
            "account_key": normalized,
            "masked_account": _mask_account(normalized),
            "bank_code": _bank_code(normalized),
            "currency": str(row.get("default_currency") or row.get("currency") or ""),
        })
    return list(accounts.values())


def project_batch_to_graph(conn: sqlite3.Connection, graph_client: GraphClient,
                           batch_id: str | None = None) -> dict:
    """Project the relational records into LadybugDB (idempotent rebuild).

    ``batch_id`` is accepted for API compatibility; the projection always
    reflects the full relational system of record so multi-batch patterns
    (shared bank accounts across vendors from different uploads) stay visible.
    """
    started = time.perf_counter()
    rebuild_graph_from_db(conn, graph_client)
    from .queries import fetch_graph_stats

    stats = fetch_graph_stats(graph_client)
    return {
        "rebuilt": True,
        "duration_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "total_nodes": stats["total_nodes"],
        "total_relationships": stats["total_relationships"],
        "nodes": stats["nodes"],
        "relationships": stats["relationships"],
        "engine": stats["engine"],
    }


def ensure_graph_projected(conn: sqlite3.Connection, graph_client: GraphClient) -> dict:
    """Project once when the graph is empty; no-op on subsequent reads.

    Used by the read-only graph API surfaces and the inspect_entity_graph skill
    so a fresh process (Cloud Run cold start) reconstructs the projection from
    the relational system of record automatically.
    """
    from .queries import fetch_graph_stats
    from .schema import initialize_schema

    initialize_schema(graph_client)  # idempotent DDL — covers fresh processes
    stats = fetch_graph_stats(graph_client)
    if stats["total_nodes"] == 0:
        return project_batch_to_graph(conn, graph_client)
    return {
        "rebuilt": False,
        "duration_ms": 0.0,
        "total_nodes": stats["total_nodes"],
        "total_relationships": stats["total_relationships"],
    }


def rebuild_graph_from_db(conn: sqlite3.Connection, graph_client: GraphClient) -> dict:
    """Deterministically reconstruct the whole graph from the relational DB."""
    initialize_schema(graph_client)

    vendors = [dict(r) for r in conn.execute("SELECT * FROM vendors").fetchall()]
    approvers: list[dict] = []
    if _table_exists(conn, "approvers"):
        approvers = [dict(r) for r in conn.execute("SELECT * FROM approvers").fetchall()]
    contracts = [dict(r) for r in conn.execute("SELECT * FROM contracts").fetchall()]
    purchase_orders = [dict(r) for r in conn.execute("SELECT * FROM purchase_orders").fetchall()]
    invoice_rows = [dict(r) for r in conn.execute("SELECT * FROM invoices").fetchall()]
    payments = [dict(r) for r in conn.execute("SELECT * FROM payments").fetchall()]
    credit_notes: list[dict] = []
    if _table_exists(conn, "credit_notes"):
        credit_notes = [dict(r) for r in conn.execute("SELECT * FROM credit_notes").fetchall()]

    with graph_client.write_transaction():
        graph_client.execute_write(_CLEAR_NODES)
        _project_all(graph_client, vendors, approvers, contracts, purchase_orders,
                     invoice_rows, payments, credit_notes)

    return {
        "rebuilt": True,
        "nodes_projected": True,
        "vendors": len(vendors),
        "approvers": len(approvers),
        "contracts": len(contracts),
        "purchase_orders": len(purchase_orders),
        "invoices": len(_fold_invoices(invoice_rows)),
        "payments": len(payments),
        "credit_notes": len(credit_notes),
    }


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _project_all(client: GraphClient, vendors: list[dict], approvers: list[dict],
                 contracts: list[dict], purchase_orders: list[dict],
                 invoice_rows: list[dict], payments: list[dict],
                 credit_notes: list[dict]) -> None:
    invoices = _fold_invoices(invoice_rows)

    # --- personal-infrastructure nodes (shared across entities by design) ---
    bank_accounts: dict[str, dict] = {}
    for vendor in vendors:
        normalized = _norm_bank_account(vendor.get("bank_account"))
        if normalized:
            bank_accounts.setdefault(normalized, {
                "account_key": normalized,
                "masked_account": _mask_account(normalized),
                "bank_code": _bank_code(normalized),
                "currency": str(vendor.get("default_currency") or ""),
            })
    for approver in approvers:
        normalized = _norm_bank_account(approver.get("bank_account"))
        if normalized:
            bank_accounts.setdefault(normalized, {
                "account_key": normalized,
                "masked_account": _mask_account(normalized),
                "bank_code": _bank_code(normalized),
                "currency": "",
            })

    tax_ids: dict[str, dict] = {}
    for vendor in vendors:
        tax_id = str(_clean(vendor.get("tax_id")))
        if tax_id:
            id_type, country = _tax_meta(tax_id)
            tax_ids.setdefault(tax_id, {"tax_id": tax_id, "id_type": id_type, "country": country})

    addresses: dict[str, dict] = {}
    for row in [*vendors, *approvers]:
        raw_address = row.get("address")
        address_hash = _address_hash(raw_address)
        if not address_hash:
            continue
        city, country = _address_parts(raw_address)
        addresses.setdefault(address_hash, {
            "address_hash": address_hash,
            "normalized_address": _norm_text(raw_address),
            "city": city,
            "country": country,
        })

    for account in bank_accounts.values():
        client.execute_write(
            "CREATE (:BankAccount {account_key: $account_key, masked_account: $masked_account, "
            "bank_code: $bank_code, currency: $currency})",
            dict(account),
        )
    for tax in tax_ids.values():
        client.execute_write(
            "CREATE (:TaxIdentifier {tax_id: $tax_id, id_type: $id_type, country: $country})",
            dict(tax),
        )
    for address in addresses.values():
        client.execute_write(
            "CREATE (:Address {address_hash: $address_hash, normalized_address: $normalized_address, "
            "city: $city, country: $country})",
            dict(address),
        )

    # --- Vendor nodes + infrastructure edges ---
    for vendor in vendors:
        vendor_id = str(_clean(vendor.get("vendor_id")))
        client.execute_write(
            "CREATE (:Vendor {vendor_id: $vendor_id, name: $name, normalized_name: $normalized_name, "
            "email_domain: $email_domain, phone_normalized: $phone_normalized, status: $status})",
            {
                "vendor_id": vendor_id,
                "name": str(_clean(vendor.get("vendor_name"))),
                "normalized_name": _norm_text(vendor.get("vendor_name")).upper(),
                "email_domain": _email_domain(vendor.get("email")),
                "phone_normalized": _norm_phone(vendor.get("phone")),
                "status": str(_clean(vendor.get("status"))),
            },
        )
        normalized_account = _norm_bank_account(vendor.get("bank_account"))
        if normalized_account:
            client.execute_write(
                "MATCH (v:Vendor), (b:BankAccount) WHERE v.vendor_id = $vendor_id AND b.account_key = $account_key "
                "CREATE (v)-[:USES_BANK {first_seen: $first_seen}]->(b)",
                {"vendor_id": vendor_id, "account_key": normalized_account,
                 "first_seen": str(_clean(vendor.get("first_seen")))},
            )
        tax_id = str(_clean(vendor.get("tax_id")))
        if tax_id:
            client.execute_write(
                "MATCH (v:Vendor), (t:TaxIdentifier) WHERE v.vendor_id = $vendor_id AND t.tax_id = $tax_id "
                "CREATE (v)-[:HAS_TAX_ID]->(t)",
                {"vendor_id": vendor_id, "tax_id": tax_id},
            )
        address_hash = _address_hash(vendor.get("address"))
        if address_hash:
            client.execute_write(
                "MATCH (v:Vendor), (a:Address) WHERE v.vendor_id = $vendor_id AND a.address_hash = $address_hash "
                "CREATE (v)-[:LOCATED_AT]->(a)",
                {"vendor_id": vendor_id, "address_hash": address_hash},
            )

    # --- Approver nodes + infrastructure edges ---
    for approver in approvers:
        approver_id = str(_clean(approver.get("approver_id")))
        client.execute_write(
            "CREATE (:Approver {approver_id: $approver_id, name: $name, email: $email, "
            "phone_normalized: $phone_normalized, address_hash: $address_hash, approval_limit: $approval_limit})",
            {
                "approver_id": approver_id,
                "name": str(_clean(approver.get("name"))),
                "email": str(_clean(approver.get("email"))),
                "phone_normalized": _norm_phone(approver.get("phone")),
                "address_hash": _address_hash(approver.get("address")),
                "approval_limit": float(approver.get("approval_limit") or 0.0),
            },
        )
        normalized_account = _norm_bank_account(approver.get("bank_account"))
        if normalized_account:
            client.execute_write(
                "MATCH (a:Approver), (b:BankAccount) WHERE a.approver_id = $approver_id AND b.account_key = $account_key "
                "CREATE (a)-[:APPROVER_USES_BANK]->(b)",
                {"approver_id": approver_id, "account_key": normalized_account},
            )
        address_hash = _address_hash(approver.get("address"))
        if address_hash:
            client.execute_write(
                "MATCH (a:Approver), (addr:Address) WHERE a.approver_id = $approver_id AND addr.address_hash = $address_hash "
                "CREATE (a)-[:APPROVER_LOCATED_AT]->(addr)",
                {"approver_id": approver_id, "address_hash": address_hash},
            )

    # --- Contract nodes + amendment lineage ---
    for contract in contracts:
        client.execute_write(
            "CREATE (:Contract {contract_id: $contract_id, vendor_id: $vendor_id, "
            "effective_date: $effective_date, expiry_date: $expiry_date, status: $status, "
            "unit_rate: $unit_rate, currency: $currency, item_key: $item_key, version: $version})",
            {
                "contract_id": str(_clean(contract.get("contract_id"))),
                "vendor_id": str(_clean(contract.get("vendor_id"))),
                "effective_date": str(_clean(contract.get("start_date"))),
                "expiry_date": str(_clean(contract.get("end_date"))),
                "status": str(_clean(contract.get("status"))),
                "unit_rate": float(contract.get("contracted_unit_price") or 0.0),
                "currency": str(_clean(contract.get("currency"))),
                "item_key": _norm_item(contract.get("item")),
                "version": int(contract.get("version") or 1),
            },
        )
    for contract in contracts:
        amends_id = str(_clean(contract.get("amends_contract_id")))
        if not amends_id:
            continue
        contract_id = str(_clean(contract.get("contract_id")))
        rate_delta = float(contract.get("contracted_unit_price") or 0.0) - float(
            next((float(c.get("contracted_unit_price") or 0.0) for c in contracts
                  if str(c.get("contract_id")) == amends_id), 0.0)
        )
        client.execute_write(
            "MATCH (c_new:Contract), (c_old:Contract) "
            "WHERE c_new.contract_id = $new_id AND c_old.contract_id = $old_id "
            "CREATE (c_new)-[:AMENDS {amendment_date: $amendment_date, rate_delta: $rate_delta}]->(c_old)",
            {
                "new_id": contract_id,
                "old_id": amends_id,
                "amendment_date": str(_clean(contract.get("start_date"))),
                "rate_delta": rate_delta,
            },
        )

    # --- PurchaseOrder nodes ---
    for po in purchase_orders:
        client.execute_write(
            "CREATE (:PurchaseOrder {po_id: $po_id, vendor_id: $vendor_id, item_key: $item_key, "
            "ordered_qty: $ordered_qty, unit_price: $unit_price, total_amount: $total_amount, "
            "currency: $currency, status: $status})",
            {
                "po_id": f"{_clean(po.get('po_id'))}#{int(po.get('po_line') or 1)}",
                "vendor_id": str(_clean(po.get("vendor_id"))),
                "item_key": _norm_item(po.get("item")),
                "ordered_qty": float(po.get("quantity") or 0.0),
                "unit_price": float(po.get("unit_price") or 0.0),
                "total_amount": float(po.get("quantity") or 0.0) * float(po.get("unit_price") or 0.0),
                "currency": str(_clean(po.get("currency"))),
                "status": str(_clean(po.get("status"))),
            },
        )

    # --- Invoice + InvoiceLine nodes and their edges ---
    for number, header in invoices.items():
        client.execute_write(
            "CREATE (:Invoice {invoice_id: $invoice_id, batch_id: $batch_id, "
            "invoice_number: $invoice_number, vendor_id: $vendor_id, invoice_date: $invoice_date, "
            "grand_total: $grand_total, currency: $currency, status: $status})",
            {
                "invoice_id": header["invoice_id"],
                "batch_id": header["batch_id"],
                "invoice_number": header["invoice_number"],
                "vendor_id": header["vendor_id"],
                "invoice_date": header["invoice_date"],
                "grand_total": round(header["grand_total"], 2),
                "currency": header["currency"],
                "status": header["status"],
            },
        )
        client.execute_write(
            "MATCH (i:Invoice), (v:Vendor) WHERE i.invoice_id = $invoice_id AND v.vendor_id = $vendor_id "
            "CREATE (i)-[:ISSUED_BY]->(v)",
            {"invoice_id": header["invoice_id"], "vendor_id": header["vendor_id"]},
        )
        if header["po_id"]:
            client.execute_write(
                "MATCH (i:Invoice), (p:PurchaseOrder) WHERE i.invoice_id = $invoice_id AND p.po_id STARTS WITH $po_id "
                "CREATE (i)-[:BILLED_UNDER_PO]->(p)",
                {"invoice_id": header["invoice_id"], "po_id": header["po_id"]},
            )
        for line in header["lines"]:
            client.execute_write(
                "CREATE (:InvoiceLine {line_id: $line_id, invoice_id: $invoice_id, item_key: $item_key, "
                "description: $description, quantity: $quantity, unit_price: $unit_price, "
                "line_total: $line_total})",
                {
                    "line_id": line["line_id"],
                    "invoice_id": header["invoice_id"],
                    "item_key": line["item_key"],
                    "description": line["description"],
                    "quantity": line["quantity"],
                    "unit_price": line["unit_price"],
                    "line_total": line["line_total"],
                },
            )
            client.execute_write(
                "MATCH (i:Invoice), (l:InvoiceLine) WHERE i.invoice_id = $invoice_id AND l.line_id = $line_id "
                "CREATE (i)-[:HAS_LINE]->(l)",
                {"invoice_id": header["invoice_id"], "line_id": line["line_id"]},
            )

    # --- GOVERNED_BY: invoice -> same (vendor, item, date-window) contracts ---
    contract_index: dict[tuple[str, str], list[dict]] = {}
    for contract in contracts:
        key = (str(_clean(contract.get("vendor_id"))), _norm_item(contract.get("item")))
        contract_index.setdefault(key, []).append(contract)
    for number, header in invoices.items():
        for line in header["lines"]:
            for contract in contract_index.get((header["vendor_id"], line["item_key"]), []):
                if not _in_window(header["invoice_date"],
                                  str(_clean(contract.get("start_date"))),
                                  str(_clean(contract.get("end_date")))):
                    continue
                client.execute_write(
                    "MATCH (i:Invoice), (c:Contract) WHERE i.invoice_id = $invoice_id AND c.contract_id = $contract_id "
                    "CREATE (i)-[:GOVERNED_BY]->(c)",
                    {"invoice_id": header["invoice_id"],
                     "contract_id": str(_clean(contract.get("contract_id")))},
                )

    # --- Payment nodes + settlement edges ---
    for payment in payments:
        client.execute_write(
            "CREATE (:Payment {payment_id: $payment_id, invoice_id: $invoice_id, paid_date: $paid_date, "
            "amount: $amount, currency: $currency, account_key: $account_key})",
            {
                "payment_id": str(_clean(payment.get("payment_id"))),
                "invoice_id": str(_clean(payment.get("invoice_number"))),
                "paid_date": str(_clean(payment.get("payment_date"))),
                "amount": float(payment.get("amount") or 0.0),
                "currency": str(_clean(payment.get("currency"))),
                "account_key": _norm_bank_account(payment.get("account_key")),
            },
        )
        client.execute_write(
            "MATCH (i:Invoice), (p:Payment) WHERE i.invoice_id = $invoice_id AND p.payment_id = $payment_id "
            "CREATE (i)-[:SETTLED_BY]->(p)",
            {"invoice_id": str(_clean(payment.get("invoice_number"))),
             "payment_id": str(_clean(payment.get("payment_id")))},
        )
        account_key = _norm_bank_account(payment.get("account_key"))
        if account_key:
            client.execute_write(
                "MATCH (p:Payment), (b:BankAccount) WHERE p.payment_id = $payment_id AND b.account_key = $account_key "
                "CREATE (p)-[:PAID_TO_ACCOUNT]->(b)",
                {"payment_id": str(_clean(payment.get("payment_id"))), "account_key": account_key},
            )

    # --- CreditNote nodes + vendor issuance edges ---
    for note in credit_notes:
        client.execute_write(
            "CREATE (:CreditNote {credit_note_id: $credit_note_id, vendor_id: $vendor_id, "
            "issue_date: $issue_date, amount: $amount, currency: $currency, applied_status: $applied_status})",
            {
                "credit_note_id": str(_clean(note.get("credit_note_id"))),
                "vendor_id": str(_clean(note.get("vendor_id"))),
                "issue_date": str(_clean(note.get("issue_date"))),
                "amount": float(note.get("amount") or 0.0),
                "currency": str(_clean(note.get("currency"))),
                "applied_status": str(_clean(note.get("applied_status"))),
            },
        )
        client.execute_write(
            "MATCH (v:Vendor), (c:CreditNote) WHERE v.vendor_id = $vendor_id AND c.credit_note_id = $credit_note_id "
            "CREATE (v)-[:ISSUED_CREDIT]->(c)",
            {"vendor_id": str(_clean(note.get("vendor_id"))),
             "credit_note_id": str(_clean(note.get("credit_note_id")))},
        )

    # --- APPROVED_INVOICE edges from invoices.approver_id ---
    for number, header in invoices.items():
        if not header["approver_id"]:
            continue
        client.execute_write(
            "MATCH (a:Approver), (i:Invoice) WHERE a.approver_id = $approver_id AND i.invoice_id = $invoice_id "
            "CREATE (a)-[:APPROVED_INVOICE {approved_at: $approved_at}]->(i)",
            {"approver_id": header["approver_id"], "invoice_id": header["invoice_id"],
             "approved_at": header["invoice_date"]},
        )
