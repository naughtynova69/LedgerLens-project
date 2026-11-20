"""Parameterized Cypher queries for the deterministic graph rules and API.

Every rule query expresses the multi-hop STRUCTURAL pattern (the part tabular
rules cannot see: shared BankAccount / TaxIdentifier / Address nodes, AMENDS
lineage). Amount math and date-window enforcement are re-verified in pure
Python inside the rules so numbers stay exactly reproducible. No query ever
interpolates user input — everything is bound via ``$parameters``.
"""
from __future__ import annotations

from datetime import date
import re

from .client import GraphClient
from .subgraph import build_subgraph, make_edge, make_node
from .types import GraphEvidence

R6_DRIFT_LIMIT = 0.005          # grand totals may differ by at most 0.5% (mirrors R1)
R6_MAX_DATE_GAP_DAYS = 30
R6_SPLIT_WINDOW_DAYS = 7
R6_SPLIT_BAND_LOW = 0.80        # invoice sits just below the approver limit
R6_SPLIT_BAND_HIGH = 0.999
R8_RATE_MATCH_TOLERANCE = 0.005

# ---------------------------------------------------------------------------
# R6 — cross-entity duplicate & threshold-splitting (master-prompt §4 R6)
# ---------------------------------------------------------------------------

R6_CROSS_ENTITY_DUPLICATE_QUERY = """
MATCH (i1:Invoice)-[:ISSUED_BY]->(v1:Vendor)-[:USES_BANK]->(b:BankAccount)
      <-[:USES_BANK]-(v2:Vendor)<-[:ISSUED_BY]-(i2:Invoice)
WHERE v1.vendor_id < v2.vendor_id
  AND i1.invoice_id < i2.invoice_id
  AND i1.grand_total > 0
  AND i2.grand_total > 0
  AND (abs(i1.grand_total - i2.grand_total)
       / CASE WHEN i1.grand_total > i2.grand_total
              THEN i1.grand_total ELSE i2.grand_total END) <= $drift
RETURN
  i1.invoice_id     AS invoice_id_a, i1.invoice_number AS invoice_number_a,
  i1.invoice_date   AS invoice_date_a, i1.grand_total AS grand_total_a,
  i1.currency       AS currency_a, i1.batch_id AS batch_id_a,
  i2.invoice_id     AS invoice_id_b, i2.invoice_number AS invoice_number_b,
  i2.invoice_date   AS invoice_date_b, i2.grand_total AS grand_total_b,
  i2.currency       AS currency_b, i2.batch_id AS batch_id_b,
  v1.vendor_id      AS vendor_id_a, v1.name AS vendor_name_a,
  v2.vendor_id      AS vendor_id_b, v2.name AS vendor_name_b,
  b.account_key     AS shared_account_key, b.masked_account AS masked_account
"""

R6_CROSS_ENTITY_DUPLICATE_TAX_QUERY = """
MATCH (i1:Invoice)-[:ISSUED_BY]->(v1:Vendor)-[:HAS_TAX_ID]->(t:TaxIdentifier)
      <-[:HAS_TAX_ID]-(v2:Vendor)<-[:ISSUED_BY]-(i2:Invoice)
WHERE v1.vendor_id < v2.vendor_id
  AND i1.invoice_id < i2.invoice_id
  AND i1.grand_total > 0
  AND i2.grand_total > 0
  AND (abs(i1.grand_total - i2.grand_total)
       / CASE WHEN i1.grand_total > i2.grand_total
              THEN i1.grand_total ELSE i2.grand_total END) <= $drift
RETURN
  i1.invoice_id     AS invoice_id_a, i1.invoice_number AS invoice_number_a,
  i1.invoice_date   AS invoice_date_a, i1.grand_total AS grand_total_a,
  i1.currency       AS currency_a, i1.batch_id AS batch_id_a,
  i2.invoice_id     AS invoice_id_b, i2.invoice_number AS invoice_number_b,
  i2.invoice_date   AS invoice_date_b, i2.grand_total AS grand_total_b,
  i2.currency       AS currency_b, i2.batch_id AS batch_id_b,
  v1.vendor_id      AS vendor_id_a, v1.name AS vendor_name_a,
  v2.vendor_id      AS vendor_id_b, v2.name AS vendor_name_b,
  t.tax_id          AS shared_tax_id, t.id_type AS shared_tax_type
"""

R6_SPLIT_INVOICES_QUERY = """
MATCH (a:Approver)-[:APPROVED_INVOICE]->(i1:Invoice)
      -[:ISSUED_BY]->(v1:Vendor)-[:USES_BANK]->(b:BankAccount)
      <-[:USES_BANK]-(v2:Vendor)<-[:ISSUED_BY]-(i2:Invoice)
      <-[:APPROVED_INVOICE]-(a)
WHERE v1.vendor_id < v2.vendor_id
  AND a.approval_limit > 0
  AND i1.grand_total >= $band_low * a.approval_limit
  AND i1.grand_total <= $band_high * a.approval_limit
  AND i2.grand_total >= $band_low * a.approval_limit
  AND i2.grand_total <= $band_high * a.approval_limit
RETURN
  a.approver_id AS approver_id, a.name AS approver_name, a.approval_limit AS approval_limit,
  i1.invoice_id AS invoice_id_a, i1.invoice_number AS invoice_number_a,
  i1.invoice_date AS invoice_date_a, i1.grand_total AS grand_total_a, i1.currency AS currency_a,
  i2.invoice_id AS invoice_id_b, i2.invoice_number AS invoice_number_b,
  i2.invoice_date AS invoice_date_b, i2.grand_total AS grand_total_b, i2.currency AS currency_b,
  v1.vendor_id AS vendor_id_a, v2.vendor_id AS vendor_id_b,
  b.account_key AS shared_account_key, b.masked_account AS masked_account
"""

R6_SPLIT_INVOICES_TAX_QUERY = """
MATCH (a:Approver)-[:APPROVED_INVOICE]->(i1:Invoice)
      -[:ISSUED_BY]->(v1:Vendor)-[:HAS_TAX_ID]->(t:TaxIdentifier)
      <-[:HAS_TAX_ID]-(v2:Vendor)<-[:ISSUED_BY]-(i2:Invoice)
      <-[:APPROVED_INVOICE]-(a)
WHERE v1.vendor_id < v2.vendor_id
  AND a.approval_limit > 0
  AND i1.grand_total >= $band_low * a.approval_limit
  AND i1.grand_total <= $band_high * a.approval_limit
  AND i2.grand_total >= $band_low * a.approval_limit
  AND i2.grand_total <= $band_high * a.approval_limit
RETURN
  a.approver_id AS approver_id, a.name AS approver_name, a.approval_limit AS approval_limit,
  i1.invoice_id AS invoice_id_a, i1.invoice_number AS invoice_number_a,
  i1.invoice_date AS invoice_date_a, i1.grand_total AS grand_total_a, i1.currency AS currency_a,
  i2.invoice_id AS invoice_id_b, i2.invoice_number AS invoice_number_b,
  i2.invoice_date AS invoice_date_b, i2.grand_total AS grand_total_b, i2.currency AS currency_b,
  v1.vendor_id AS vendor_id_a, v2.vendor_id AS vendor_id_b,
  t.tax_id AS shared_tax_id, t.id_type AS shared_tax_type
"""

# ---------------------------------------------------------------------------
# R7 — approver-vendor collusion (master-prompt §4 R7)
# ---------------------------------------------------------------------------

R7_COLLUSION_SHARED_BANK_QUERY = """
MATCH (a:Approver)-[:APPROVED_INVOICE]->(i:Invoice)
      -[:ISSUED_BY]->(v:Vendor)-[:USES_BANK]->(b:BankAccount)
      <-[:APPROVER_USES_BANK]-(a)
RETURN
  a.approver_id AS approver_id, a.name AS approver_name,
  i.invoice_id AS invoice_id, i.invoice_number AS invoice_number,
  i.invoice_date AS invoice_date, i.grand_total AS invoice_total, i.currency AS currency,
  i.status AS invoice_status, i.batch_id AS batch_id,
  v.vendor_id AS vendor_id, v.name AS vendor_name,
  b.account_key AS shared_account_key, b.masked_account AS masked_account
"""

R7_COLLUSION_SHARED_ADDRESS_QUERY = """
MATCH (a:Approver)-[:APPROVED_INVOICE]->(i:Invoice)
      -[:ISSUED_BY]->(v:Vendor)-[:LOCATED_AT]->(addr:Address)
      <-[:APPROVER_LOCATED_AT]-(a)
RETURN
  a.approver_id AS approver_id, a.name AS approver_name,
  i.invoice_id AS invoice_id, i.invoice_number AS invoice_number,
  i.invoice_date AS invoice_date, i.grand_total AS invoice_total, i.currency AS currency,
  i.status AS invoice_status, i.batch_id AS batch_id,
  v.vendor_id AS vendor_id, v.name AS vendor_name,
  addr.address_hash AS shared_address_hash, addr.normalized_address AS shared_address
"""

R7_COLLUSION_SHARED_PHONE_QUERY = """
MATCH (a:Approver)-[:APPROVED_INVOICE]->(i:Invoice)
      -[:ISSUED_BY]->(v:Vendor)
WHERE a.phone_normalized <> ''
  AND v.phone_normalized <> ''
  AND a.phone_normalized = v.phone_normalized
RETURN
  a.approver_id AS approver_id, a.name AS approver_name,
  i.invoice_id AS invoice_id, i.invoice_number AS invoice_number,
  i.invoice_date AS invoice_date, i.grand_total AS invoice_total, i.currency AS currency,
  i.status AS invoice_status, i.batch_id AS batch_id,
  v.vendor_id AS vendor_id, v.name AS vendor_name,
  a.phone_normalized AS shared_phone
"""

# ---------------------------------------------------------------------------
# R8 — contract lineage & unapplied credits (master-prompt §4 R8)
# ---------------------------------------------------------------------------

R8_SUPERSEDED_RATE_QUERY = """
MATCH (c_new:Contract)-[:AMENDS*1..5]->(c_old:Contract)
      <-[:GOVERNED_BY]-(i:Invoice)-[:HAS_LINE]->(l:InvoiceLine)
WHERE c_new.unit_rate < c_old.unit_rate
  AND c_old.unit_rate > 0
RETURN
  c_new.contract_id AS new_contract_id, c_new.unit_rate AS new_rate,
  c_new.effective_date AS new_effective_date, c_new.status AS new_status, c_new.version AS new_version,
  c_old.contract_id AS old_contract_id, c_old.unit_rate AS old_rate,
  c_old.currency AS currency, c_old.item_key AS item_key,
  i.invoice_id AS invoice_id, i.invoice_number AS invoice_number,
  i.invoice_date AS invoice_date, i.status AS invoice_status, i.batch_id AS batch_id,
  l.line_id AS line_id, l.quantity AS quantity, l.unit_price AS line_unit_price,
  l.line_total AS line_total
"""

R8_UNAPPLIED_CREDITS_QUERY = """
MATCH (v:Vendor)-[:ISSUED_CREDIT]->(cn:CreditNote)
WHERE cn.applied_status = 'OPEN'
MATCH (i:Invoice)-[:ISSUED_BY]->(v)
WHERE i.invoice_date >= cn.issue_date
RETURN
  v.vendor_id AS vendor_id, v.name AS vendor_name,
  cn.credit_note_id AS credit_note_id, cn.issue_date AS credit_note_issue_date,
  cn.amount AS credit_note_amount, cn.currency AS credit_note_currency,
  i.invoice_id AS invoice_id, i.invoice_number AS invoice_number,
  i.invoice_date AS invoice_date, i.grand_total AS invoice_total,
  i.status AS invoice_status, i.batch_id AS batch_id
"""

# ---------------------------------------------------------------------------
# Entity neighborhood & stats (master-prompt §5.2)
# ---------------------------------------------------------------------------

# Whitelisted (node label, primary-key column) pairs — the neighborhood lookup
# never interpolates anything outside this map.
ENTITY_PRIMARY_KEYS: dict[str, str] = {
    "Vendor": "vendor_id",
    "BankAccount": "account_key",
    "TaxIdentifier": "tax_id",
    "Address": "address_hash",
    "Approver": "approver_id",
    "Contract": "contract_id",
    "PurchaseOrder": "po_id",
    "Invoice": "invoice_id",
    "InvoiceLine": "line_id",
    "Payment": "payment_id",
    "CreditNote": "credit_note_id",
}

ONE_HOP_OUT_QUERY = (
    "MATCH (e:{label}) WHERE e.{pk} = $entity_id "
    "MATCH (e)-[r]->(x) "
    "RETURN x AS neighbor, label(x) AS neighbor_label, type(r) AS rel_type, "
    "properties(r) AS rel_properties"
)

ONE_HOP_IN_QUERY = (
    "MATCH (e:{label}) WHERE e.{pk} = $entity_id "
    "MATCH (e)<-[r]-(x) "
    "RETURN x AS neighbor, label(x) AS neighbor_label, type(r) AS rel_type, "
    "properties(r) AS rel_properties"
)

GRAPH_STATS_QUERIES: list[tuple[str, str, str]] = [
    # (kind, label/type, query)
    ("node", "Vendor", "MATCH (n:Vendor) RETURN count(n) AS n;"),
    ("node", "BankAccount", "MATCH (n:BankAccount) RETURN count(n) AS n;"),
    ("node", "TaxIdentifier", "MATCH (n:TaxIdentifier) RETURN count(n) AS n;"),
    ("node", "Address", "MATCH (n:Address) RETURN count(n) AS n;"),
    ("node", "Approver", "MATCH (n:Approver) RETURN count(n) AS n;"),
    ("node", "Contract", "MATCH (n:Contract) RETURN count(n) AS n;"),
    ("node", "PurchaseOrder", "MATCH (n:PurchaseOrder) RETURN count(n) AS n;"),
    ("node", "Invoice", "MATCH (n:Invoice) RETURN count(n) AS n;"),
    ("node", "InvoiceLine", "MATCH (n:InvoiceLine) RETURN count(n) AS n;"),
    ("node", "Payment", "MATCH (n:Payment) RETURN count(n) AS n;"),
    ("node", "CreditNote", "MATCH (n:CreditNote) RETURN count(n) AS n;"),
    ("rel", "USES_BANK", "MATCH ()-[r:USES_BANK]->() RETURN count(r) AS n;"),
    ("rel", "HAS_TAX_ID", "MATCH ()-[r:HAS_TAX_ID]->() RETURN count(r) AS n;"),
    ("rel", "LOCATED_AT", "MATCH ()-[r:LOCATED_AT]->() RETURN count(r) AS n;"),
    ("rel", "ISSUED_BY", "MATCH ()-[r:ISSUED_BY]->() RETURN count(r) AS n;"),
    ("rel", "HAS_LINE", "MATCH ()-[r:HAS_LINE]->() RETURN count(r) AS n;"),
    ("rel", "BILLED_UNDER_PO", "MATCH ()-[r:BILLED_UNDER_PO]->() RETURN count(r) AS n;"),
    ("rel", "GOVERNED_BY", "MATCH ()-[r:GOVERNED_BY]->() RETURN count(r) AS n;"),
    ("rel", "AMENDS", "MATCH ()-[r:AMENDS]->() RETURN count(r) AS n;"),
    ("rel", "SETTLED_BY", "MATCH ()-[r:SETTLED_BY]->() RETURN count(r) AS n;"),
    ("rel", "PAID_TO_ACCOUNT", "MATCH ()-[r:PAID_TO_ACCOUNT]->() RETURN count(r) AS n;"),
    ("rel", "ISSUED_CREDIT", "MATCH ()-[r:ISSUED_CREDIT]->() RETURN count(r) AS n;"),
    ("rel", "APPLIED_TO_INVOICE", "MATCH ()-[r:APPLIED_TO_INVOICE]->() RETURN count(r) AS n;"),
    ("rel", "APPROVED_INVOICE", "MATCH ()-[r:APPROVED_INVOICE]->() RETURN count(r) AS n;"),
    ("rel", "APPROVER_USES_BANK", "MATCH ()-[r:APPROVER_USES_BANK]->() RETURN count(r) AS n;"),
    ("rel", "APPROVER_LOCATED_AT", "MATCH ()-[r:APPROVER_LOCATED_AT]->() RETURN count(r) AS n;"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _date_gap(a, b) -> int | None:
    da, db = _iso_date(a), _iso_date(b)
    if da is None or db is None:
        return None
    return abs((da - db).days)


def _norm_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    return digits[-10:] if len(digits) >= 10 else digits


# ---------------------------------------------------------------------------
# Evidence fetchers
# ---------------------------------------------------------------------------

def _r6_duplicate_row_to_evidence(row: dict, shared_via: str) -> dict:
    """Shape one cross-entity duplicate match with its proof subgraph."""
    nodes = [
        make_node(f"Invoice:{row['invoice_id_a']}", "Invoice", row["invoice_number_a"],
                  {"invoice_date": row["invoice_date_a"], "grand_total": row["grand_total_a"],
                   "currency": row["currency_a"], "batch_id": row["batch_id_a"]}, highlight=True),
        make_node(f"Invoice:{row['invoice_id_b']}", "Invoice", row["invoice_number_b"],
                  {"invoice_date": row["invoice_date_b"], "grand_total": row["grand_total_b"],
                   "currency": row["currency_b"], "batch_id": row["batch_id_b"]}, highlight=True),
        make_node(f"Vendor:{row['vendor_id_a']}", "Vendor", row["vendor_name_a"],
                  {"vendor_id": row["vendor_id_a"]}),
        make_node(f"Vendor:{row['vendor_id_b']}", "Vendor", row["vendor_name_b"],
                  {"vendor_id": row["vendor_id_b"]}),
    ]
    edges = [
        make_edge(f"Invoice:{row['invoice_id_a']}", f"Vendor:{row['vendor_id_a']}", "ISSUED_BY"),
        make_edge(f"Invoice:{row['invoice_id_b']}", f"Vendor:{row['vendor_id_b']}", "ISSUED_BY"),
    ]
    if shared_via == "bank":
        nodes.append(make_node(f"BankAccount:{row['shared_account_key']}", "BankAccount",
                               row.get("masked_account") or row["shared_account_key"],
                               {"account_key": row["shared_account_key"]}, highlight=True))
        edges.append(make_edge(f"Vendor:{row['vendor_id_a']}", f"BankAccount:{row['shared_account_key']}", "USES_BANK"))
        edges.append(make_edge(f"Vendor:{row['vendor_id_b']}", f"BankAccount:{row['shared_account_key']}", "USES_BANK"))
        shared_ref = row["shared_account_key"]
    else:
        nodes.append(make_node(f"TaxIdentifier:{row['shared_tax_id']}", "TaxIdentifier",
                               row["shared_tax_id"], {"tax_id": row["shared_tax_id"],
                                                      "id_type": row["shared_tax_type"]}, highlight=True))
        edges.append(make_edge(f"Vendor:{row['vendor_id_a']}", f"TaxIdentifier:{row['shared_tax_id']}", "HAS_TAX_ID"))
        edges.append(make_edge(f"Vendor:{row['vendor_id_b']}", f"TaxIdentifier:{row['shared_tax_id']}", "HAS_TAX_ID"))
        shared_ref = row["shared_tax_id"]

    return {
        "shared_via": shared_via,
        "shared_ref": shared_ref,
        "vendor_ids": [row["vendor_id_a"], row["vendor_id_b"]],
        "invoice_ids": [row["invoice_id_a"], row["invoice_id_b"]],
        "invoice_numbers": [row["invoice_number_a"], row["invoice_number_b"]],
        "invoice_dates": [row["invoice_date_a"], row["invoice_date_b"]],
        "grand_totals": [float(row["grand_total_a"]), float(row["grand_total_b"])],
        "currency": row["currency_a"] or row["currency_b"],
        "batch_ids": [row["batch_id_a"], row["batch_id_b"]],
        "proof_subgraph": build_subgraph(
            nodes, edges,
            cypher_rule="R6_CROSS_ENTITY_DUPLICATE",
            summary=(
                f"Invoices {row['invoice_number_a']} ({row['vendor_id_a']}) and "
                f"{row['invoice_number_b']} ({row['vendor_id_b']}) route to shared "
                f"{shared_via} {shared_ref}."
            ),
        ),
    }


def _split_row_to_evidence(row: dict, shared_via: str) -> dict:
    shared_ref = row.get("shared_account_key") or row.get("shared_tax_id") or ""
    nodes = [
        make_node(f"Approver:{row['approver_id']}", "Approver", row["approver_name"],
                  {"approval_limit": row["approval_limit"]}),
        make_node(f"Invoice:{row['invoice_id_a']}", "Invoice", row["invoice_number_a"],
                  {"invoice_date": row["invoice_date_a"], "grand_total": row["grand_total_a"],
                   "currency": row["currency_a"]}, highlight=True),
        make_node(f"Invoice:{row['invoice_id_b']}", "Invoice", row["invoice_number_b"],
                  {"invoice_date": row["invoice_date_b"], "grand_total": row["grand_total_b"],
                   "currency": row["currency_b"]}, highlight=True),
        make_node(f"Vendor:{row['vendor_id_a']}", "Vendor", row["vendor_id_a"], {}),
        make_node(f"Vendor:{row['vendor_id_b']}", "Vendor", row["vendor_id_b"], {}),
    ]
    edges = [
        make_edge(f"Approver:{row['approver_id']}", f"Invoice:{row['invoice_id_a']}", "APPROVED_INVOICE"),
        make_edge(f"Approver:{row['approver_id']}", f"Invoice:{row['invoice_id_b']}", "APPROVED_INVOICE"),
        make_edge(f"Invoice:{row['invoice_id_a']}", f"Vendor:{row['vendor_id_a']}", "ISSUED_BY"),
        make_edge(f"Invoice:{row['invoice_id_b']}", f"Vendor:{row['vendor_id_b']}", "ISSUED_BY"),
        make_edge(f"Vendor:{row['vendor_id_a']}",
                  (f"BankAccount:{shared_ref}" if shared_via == "bank" else f"TaxIdentifier:{shared_ref}"),
                  "USES_BANK" if shared_via == "bank" else "HAS_TAX_ID"),
        make_edge(f"Vendor:{row['vendor_id_b']}",
                  (f"BankAccount:{shared_ref}" if shared_via == "bank" else f"TaxIdentifier:{shared_ref}"),
                  "USES_BANK" if shared_via == "bank" else "HAS_TAX_ID"),
    ]
    if shared_via == "bank":
        nodes.append(make_node(f"BankAccount:{shared_ref}", "BankAccount",
                               row.get("masked_account") or shared_ref,
                               {"account_key": shared_ref}, highlight=True))
    else:
        nodes.append(make_node(f"TaxIdentifier:{shared_ref}", "TaxIdentifier", shared_ref,
                               {"tax_id": shared_ref}, highlight=True))

    return {
        "shared_via": shared_via,
        "shared_ref": shared_ref,
        "approver_id": row["approver_id"],
        "approver_name": row["approver_name"],
        "approval_limit": float(row["approval_limit"]),
        "vendor_ids": [row["vendor_id_a"], row["vendor_id_b"]],
        "invoice_ids": [row["invoice_id_a"], row["invoice_id_b"]],
        "invoice_numbers": [row["invoice_number_a"], row["invoice_number_b"]],
        "invoice_dates": [row["invoice_date_a"], row["invoice_date_b"]],
        "grand_totals": [float(row["grand_total_a"]), float(row["grand_total_b"])],
        "currency": row["currency_a"] or row["currency_b"],
        "batch_ids": [],
        "proof_subgraph": build_subgraph(nodes, edges, cypher_rule="R6_SPLIT_INVOICES",
                                         summary="Split invoices around an approval limit."),
    }


def _collusion_row_to_evidence(row: dict) -> dict:
    invoice_id = row["invoice_id"]
    vendor_id = row["vendor_id"]
    approver_id = row["approver_id"]
    nodes = [
        make_node(f"Approver:{approver_id}", "Approver", row["approver_name"], {}),
        make_node(f"Invoice:{invoice_id}", "Invoice", row["invoice_number"],
                  {"invoice_date": row["invoice_date"], "grand_total": row["invoice_total"],
                   "currency": row["currency"], "status": row["invoice_status"],
                   "batch_id": row["batch_id"]}, highlight=True),
        make_node(f"Vendor:{vendor_id}", "Vendor", row["vendor_name"], {}, highlight=True),
    ]
    edges = [
        make_edge(f"Approver:{approver_id}", f"Invoice:{invoice_id}", "APPROVED_INVOICE"),
        make_edge(f"Invoice:{invoice_id}", f"Vendor:{vendor_id}", "ISSUED_BY"),
    ]
    if row.get("shared_account_key"):
        vector = "bank"
        shared_ref = row["shared_account_key"]
        nodes.append(make_node(f"BankAccount:{shared_ref}", "BankAccount",
                               row.get("masked_account") or shared_ref,
                               {"account_key": shared_ref}, highlight=True))
        edges.append(make_edge(f"Vendor:{vendor_id}", f"BankAccount:{shared_ref}", "USES_BANK"))
        edges.append(make_edge(f"Approver:{approver_id}", f"BankAccount:{shared_ref}", "APPROVER_USES_BANK"))
    elif row.get("shared_address_hash"):
        vector = "address"
        shared_ref = row["shared_address_hash"]
        nodes.append(make_node(f"Address:{shared_ref}", "Address",
                               row.get("shared_address") or shared_ref,
                               {"address_hash": shared_ref}, highlight=True))
        edges.append(make_edge(f"Vendor:{vendor_id}", f"Address:{shared_ref}", "LOCATED_AT"))
        edges.append(make_edge(f"Approver:{approver_id}", f"Address:{shared_ref}", "APPROVER_LOCATED_AT"))
    else:
        vector = "phone"
        shared_ref = row.get("shared_phone") or ""
        nodes[0]["properties"]["phone_normalized"] = shared_ref
        nodes[2]["properties"]["phone_normalized"] = shared_ref
        nodes[0]["properties"]["highlight"] = False
        nodes[2]["properties"]["highlight"] = True

    return {
        "vector": vector,
        "shared_ref": shared_ref,
        "approver_id": approver_id,
        "approver_name": row["approver_name"],
        "vendor_id": vendor_id,
        "vendor_name": row["vendor_name"],
        "invoice_id": invoice_id,
        "invoice_number": row["invoice_number"],
        "invoice_date": row["invoice_date"],
        "invoice_total": float(row["invoice_total"] or 0.0),
        "currency": row["currency"],
        "invoice_status": row["invoice_status"],
        "batch_ids": [row["batch_id"]],
        "proof_subgraph": build_subgraph(
            nodes, edges, cypher_rule="R7_COLLUSION",
            summary=(
                f"Approver {approver_id} approved invoice {row['invoice_number']} from "
                f"vendor {vendor_id}; both share {vector} {shared_ref}."
            ),
        ),
    }


def _superseded_row_to_evidence(row: dict) -> dict:
    nodes = [
        make_node(f"Contract:{row['new_contract_id']}", "Contract", row["new_contract_id"],
                  {"unit_rate": row["new_rate"], "effective_date": row["new_effective_date"],
                   "status": row["new_status"], "version": row["new_version"]}, highlight=True),
        make_node(f"Contract:{row['old_contract_id']}", "Contract", row["old_contract_id"],
                  {"unit_rate": row["old_rate"], "item_key": row["item_key"]}),
        make_node(f"Invoice:{row['invoice_id']}", "Invoice", row["invoice_number"],
                  {"invoice_date": row["invoice_date"], "status": row["invoice_status"],
                   "batch_id": row["batch_id"]}, highlight=True),
        make_node(f"InvoiceLine:{row['line_id']}", "InvoiceLine", row["line_id"],
                  {"quantity": row["quantity"], "unit_price": row["line_unit_price"],
                   "line_total": row["line_total"]}),
    ]
    edges = [
        make_edge(f"Contract:{row['new_contract_id']}", f"Contract:{row['old_contract_id']}", "AMENDS"),
        make_edge(f"Invoice:{row['invoice_id']}", f"Contract:{row['old_contract_id']}", "GOVERNED_BY"),
        make_edge(f"Invoice:{row['invoice_id']}", f"InvoiceLine:{row['line_id']}", "HAS_LINE"),
    ]
    return {
        "new_contract_id": row["new_contract_id"],
        "old_contract_id": row["old_contract_id"],
        "new_rate": float(row["new_rate"]),
        "old_rate": float(row["old_rate"]),
        "new_effective_date": row["new_effective_date"],
        "currency": row["currency"],
        "item_key": row["item_key"],
        "invoice_id": row["invoice_id"],
        "invoice_number": row["invoice_number"],
        "invoice_date": row["invoice_date"],
        "invoice_status": row["invoice_status"],
        "line_id": row["line_id"],
        "quantity": float(row["quantity"] or 0.0),
        "line_unit_price": float(row["line_unit_price"] or 0.0),
        "line_total": float(row["line_total"] or 0.0),
        "batch_ids": [row["batch_id"]],
        "proof_subgraph": build_subgraph(
            nodes, edges, cypher_rule="R8_SUPERSEDED_RATE",
            summary=(
                f"Invoice {row['invoice_number']} is still billed at the superseded rate "
                f"{row['old_rate']:,.2f} while amendment {row['new_contract_id']} set "
                f"{row['new_rate']:,.2f}."
            ),
        ),
    }


def _credits_row_to_evidence(row: dict) -> dict:
    nodes = [
        make_node(f"Vendor:{row['vendor_id']}", "Vendor", row["vendor_name"], {}),
        make_node(f"CreditNote:{row['credit_note_id']}", "CreditNote", row["credit_note_id"],
                  {"issue_date": row["credit_note_issue_date"], "amount": row["credit_note_amount"],
                   "currency": row["credit_note_currency"], "applied_status": "OPEN"},
                  highlight=True),
        make_node(f"Invoice:{row['invoice_id']}", "Invoice", row["invoice_number"],
                  {"invoice_date": row["invoice_date"], "grand_total": row["invoice_total"],
                   "status": row["invoice_status"], "batch_id": row["batch_id"]}),
    ]
    edges = [
        make_edge(f"Vendor:{row['vendor_id']}", f"CreditNote:{row['credit_note_id']}", "ISSUED_CREDIT"),
        make_edge(f"Invoice:{row['invoice_id']}", f"Vendor:{row['vendor_id']}", "ISSUED_BY"),
    ]
    return {
        "vendor_id": row["vendor_id"],
        "vendor_name": row["vendor_name"],
        "credit_note_id": row["credit_note_id"],
        "credit_note_issue_date": row["credit_note_issue_date"],
        "credit_note_amount": float(row["credit_note_amount"] or 0.0),
        "credit_note_currency": row["credit_note_currency"],
        "invoice_ids": [row["invoice_id"]],
        "invoice_numbers": [row["invoice_number"]],
        "invoice_dates": [row["invoice_date"]],
        "batch_ids": [row["batch_id"]],
        "proof_subgraph": build_subgraph(
            nodes, edges, cypher_rule="R8_UNAPPLIED_CREDITS",
            summary=(
                f"Credit note {row['credit_note_id']} ({row['credit_note_amount']:,.2f} "
                f"{row['credit_note_currency']}) is still OPEN while vendor "
                f"{row['vendor_id']} keeps billing."
            ),
        ),
    }


def fetch_graph_evidence(client: GraphClient) -> GraphEvidence:
    """Run every deterministic rule query and shape results for R6-R8.

    Structural multi-hop patterns are matched in Cypher; final date windows and
    amount math are re-verified in pure Python by the rules themselves.
    """
    evidence = GraphEvidence()

    dup_rows = client.execute_read(R6_CROSS_ENTITY_DUPLICATE_QUERY, {"drift": R6_DRIFT_LIMIT})
    dup_rows += client.execute_read(R6_CROSS_ENTITY_DUPLICATE_TAX_QUERY, {"drift": R6_DRIFT_LIMIT})
    for row in dup_rows:
        shared_via = "bank" if row.get("shared_account_key") else "tax"
        gap = _date_gap(row["invoice_date_a"], row["invoice_date_b"])
        if gap is None or gap > R6_MAX_DATE_GAP_DAYS:
            continue
        row["date_gap_days"] = gap
        evidence.cross_entity_duplicates.append(_r6_duplicate_row_to_evidence(row, shared_via))

    split_rows = client.execute_read(
        R6_SPLIT_INVOICES_QUERY,
        {"band_low": R6_SPLIT_BAND_LOW, "band_high": R6_SPLIT_BAND_HIGH},
    )
    split_rows += client.execute_read(
        R6_SPLIT_INVOICES_TAX_QUERY,
        {"band_low": R6_SPLIT_BAND_LOW, "band_high": R6_SPLIT_BAND_HIGH},
    )
    for row in split_rows:
        gap = _date_gap(row["invoice_date_a"], row["invoice_date_b"])
        if gap is None or gap > R6_SPLIT_WINDOW_DAYS:
            continue
        combined = float(row["grand_total_a"]) + float(row["grand_total_b"])
        if combined <= float(row["approval_limit"]):
            continue
        row["date_gap_days"] = gap
        shared_via = "bank" if row.get("shared_account_key") else "tax"
        evidence.split_invoices.append(_split_row_to_evidence(row, shared_via))

    for row in client.execute_read(R7_COLLUSION_SHARED_BANK_QUERY):
        evidence.collusion.append(_collusion_row_to_evidence(row))
    for row in client.execute_read(R7_COLLUSION_SHARED_ADDRESS_QUERY):
        evidence.collusion.append(_collusion_row_to_evidence(row))
    for row in client.execute_read(R7_COLLUSION_SHARED_PHONE_QUERY):
        evidence.collusion.append(_collusion_row_to_evidence(row))

    for row in client.execute_read(R8_SUPERSEDED_RATE_QUERY):
        evidence.superseded_rates.append(_superseded_row_to_evidence(row))

    credits: dict[tuple[str, str], dict] = {}
    for row in client.execute_read(R8_UNAPPLIED_CREDITS_QUERY):
        key = (row["vendor_id"], row["credit_note_id"])
        entry = credits.get(key)
        if entry is None:
            entry = _credits_row_to_evidence(row)
            credits[key] = entry
        else:
            entry["invoice_ids"].append(row["invoice_id"])
            entry["invoice_numbers"].append(row["invoice_number"])
            entry["invoice_dates"].append(row["invoice_date"])
            entry["batch_ids"].append(row["batch_id"])
    evidence.unapplied_credits = list(credits.values())

    return evidence


def fetch_graph_stats(client: GraphClient) -> dict:
    """Node/relationship counts plus engine status (never calls the LLM)."""
    counts: dict[str, dict] = {}
    for kind, label, query in GRAPH_STATS_QUERIES:
        rows = client.execute_read(query)
        value = int(rows[0]["n"]) if rows else 0
        bucket = counts.setdefault(kind, {})
        bucket[label] = value
    health = client.health_check()
    return {
        "engine": health,
        "nodes": counts.get("node", {}),
        "relationships": counts.get("rel", {}),
        "total_nodes": sum(counts.get("node", {}).values()),
        "total_relationships": sum(counts.get("rel", {}).values()),
    }


def fetch_entity_neighborhood(client: GraphClient, entity_type: str, entity_id: str,
                              hops: int = 2) -> dict:
    """Deterministic k-hop neighborhood (hops clamped to 1..3).

    Traversal is a Python BFS of 1-hop Cypher steps so node labels, rel types
    and rel properties stay fully serializable without engine-specific path
    objects. ``entity_type`` and the primary-key column come from a strict
    whitelist; ``entity_id`` is always bound as a query parameter.
    """
    if entity_type not in ENTITY_PRIMARY_KEYS:
        raise ValueError(f"unknown entity type: {entity_type}")
    hops = min(max(int(hops), 1), 3)
    pk = ENTITY_PRIMARY_KEYS[entity_type]

    def node_key(label: str, value: str) -> str:
        return f"{label}:{value}"

    start_key = node_key(entity_type, str(entity_id))
    seen_nodes: dict[str, dict] = {}
    seen_edges: dict[tuple[str, str, str], dict] = {}
    frontier = {start_key: (entity_type, str(entity_id))}

    rows_out = client.execute_read(
        ONE_HOP_OUT_QUERY.format(label=entity_type, pk=pk), {"entity_id": str(entity_id)}
    )
    rows_in = client.execute_read(
        ONE_HOP_IN_QUERY.format(label=entity_type, pk=pk), {"entity_id": str(entity_id)}
    )

    def consume(rows: list[dict], depth: int) -> dict[str, tuple[str, str]]:
        next_frontier: dict[str, tuple[str, str]] = {}
        for row in rows:
            label = row["neighbor_label"]
            neighbor = row["neighbor"]
            pk_value = str(neighbor.get(pk, ""))
            key = node_key(label, pk_value)
            seen_nodes[key] = {
                "id": key,
                "label": str(neighbor.get(pk, pk_value)),
                "type": label,
                "properties": dict(neighbor),
                "highlight": depth == 0,
            }
            source = start_key if depth == 0 else None
            edge_key = (start_key, key, row["rel_type"])
            if source is not None:
                seen_edges[edge_key] = {
                    "source": source,
                    "target": key,
                    "type": row["rel_type"],
                    "properties": dict(row["rel_properties"] or {}),
                }
            if depth + 1 < hops:
                next_frontier[key] = (label, pk_value)
        return next_frontier

    current = consume(rows_out + rows_in, 0)
    for depth in range(1, hops):
        next_frontier: dict[str, tuple[str, str]] = {}
        for key, (label, value) in current.items():
            rows_out = client.execute_read(
                ONE_HOP_OUT_QUERY.format(label=label, pk=ENTITY_PRIMARY_KEYS.get(label, pk)),
                {"entity_id": value},
            )
            rows_in = client.execute_read(
                ONE_HOP_IN_QUERY.format(label=label, pk=ENTITY_PRIMARY_KEYS.get(label, pk)),
                {"entity_id": value},
            )
            for row in rows_out + rows_in:
                child_label = row["neighbor_label"]
                neighbor = row["neighbor"]
                child_pk = ENTITY_PRIMARY_KEYS.get(child_label, pk)
                child_value = str(neighbor.get(child_pk, ""))
                child_key = node_key(child_label, child_value)
                if child_key not in seen_nodes:
                    seen_nodes[child_key] = {
                        "id": child_key,
                        "label": child_value,
                        "type": child_label,
                        "properties": dict(neighbor),
                        "highlight": False,
                    }
                edge_key = (key, child_key, row["rel_type"])
                if edge_key not in seen_edges:
                    seen_edges[edge_key] = {
                        "source": key,
                        "target": child_key,
                        "type": row["rel_type"],
                        "properties": dict(row["rel_properties"] or {}),
                    }
                if depth + 1 < hops:
                    next_frontier[child_key] = (child_label, child_value)
        current = next_frontier

    start_node = {
        "id": start_key,
        "label": str(entity_id),
        "type": entity_type,
        "properties": {},
        "highlight": True,
    }
    nodes = [start_node] + [n for k, n in seen_nodes.items() if k != start_key]
    edges = [
        e for e in seen_edges.values()
        if e["source"] in {n["id"] for n in nodes} and e["target"] in {n["id"] for n in nodes}
    ]
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "hops": hops,
        "nodes": nodes,
        "edges": edges,
        "cypher_rule": "ENTITY_NEIGHBORHOOD",
        "summary": f"{len(nodes)} nodes within {hops} hop(s) of {entity_type}:{entity_id}.",
    }
