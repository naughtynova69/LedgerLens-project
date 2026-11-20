# 05 · API Spec — LedgerLens backend

Base URL (dev): `http://127.0.0.1:8000` · Interactive docs: `http://127.0.0.1:8000/docs` (FastAPI auto-generates from this code).

All request/response bodies are JSON unless marked *multipart*. Error shape everywhere:

```json
{"detail": "human-readable message"}
```

## Endpoints

### `GET /health`
Liveness for Cloud Run + dashboard banner.
```json
{"status": "ok", "version": "0.1.0"}
```

### `POST /api/ingest/upload` — *multipart*
Upload a batch of source documents.
| Field | Type | Notes |
|-------|------|-------|
| `kind` | form text | `invoices` / `purchase_orders` / `contracts` / `payments` / `payment_ledger` |
| `file` | file | CSV or PDF |

Response:
```json
{"batch_id": "B-0001", "kind": "invoices", "stored": "uploads/B-0001-invoices.csv", "rows_detected": 17}
```

### `POST /api/run/{batch_id}/extract`
Run Gemini extraction over the batch (PDFs → structured JSON; CSVs → parsed & validated). Returns row counts per table. Long-running: the UI polls `GET /api/batches/{batch_id}` for status.

```json
{"batch_id": "B-0001", "state": "extracted", "invoices": 9, "contracts": 5, "purchase_orders": 7, "payments": 5}
```

### `POST /api/run/{batch_id}/detect`
Normalize + run R1–R5 over the current store. Creates `findings` rows.

```json
{"batch_id": "B-0001", "findings_created": 6, "by_rule": {"R1": 1, "R2": 1, "R3": 1, "R4": 2, "R5": 1}}
```

### `GET /api/findings?status=&severity=&rule_id=`
Exception queue, ordered by `amount_at_risk DESC`. Each item:
```json
{
  "finding_id": "F-0001",
  "rule_id": "R1",
  "title": "Possible duplicate payment",
  "severity": "critical",
  "amount_at_risk": 4956.00,
  "currency": "INR",
  "status": "open",
  "confidence": 0.93,
  "evidence": [{"source": "invoices", "record_id": "INV-8821", "field": "line_total", "value": "4956.00 INR"}],
  "explanation": {"headline": "Duplicate payment of ₹4,956", "explanation": "...", "recommended_action": "...", "limitations": "..."}
}
```

### `GET /api/findings/{finding_id}`
Full finding + joined source records (invoice lines, PO line, contract line, payment rows) for the evidence panel.

### `POST /api/findings/{finding_id}/decision`
Reviewer action. Appends to `decisions` + `audit_log`, updates finding `status`.
```json
{"action": "reject", "reviewer": "avani", "note": "Confirmed duplicate; recovery task raised."}
```
`action` ∈ `approve` / `reject` / `request_docs` / `recovery`.

### `GET /api/memo?batch_id=B-0001`
One-click audit memo (markdown text) for finance leadership: total at risk by rule, top findings, decisions taken, outstanding recovery actions. The memo is generated deterministically from stored data — Gemini optionally polishes the executive summary paragraph.

### `GET /api/batches/{batch_id}`
Status of a batch: `{state: "uploaded|extracted|detected", counts, errors[]}`.

## Graph endpoints — embedded LadybugDB knowledge graph

`LEDGERLENS_GRAPH_ENABLED=true` activates these surfaces. All responses are deterministic; `entity_type` is whitelist-clamped and every query is parameterized (no raw Cypher from clients).

### `POST /api/graph/rebuild?batch_id=B-0001`
Deterministically rebuilds the LadybugDB projection from the relational system of record. Returns:
```json
{"rebuilt": true, "duration_ms": 41.7, "total_nodes": 78, "total_relationships": 77,
 "nodes": {"Vendor": 9, "BankAccount": 3}, "relationships": {"USES_BANK": 3, "AMENDS": 1},
 "engine": {"ok": true, "engine": "ladybug", "mode": "file"}}
```
Writes an `audit_log` row (`actor='graph_api'`).

### `GET /api/graph/stats`
Counts by node label and relationship type, engine status, and `multi_hop_risks` (number of stored R6–R8 findings).

### `GET /api/graph/findings/{finding_id}/subgraph`
Evidence subgraph for any finding. R6–R8 findings return their **stored** proof subgraph (`source: "stored"`, `cypher_rule` e.g. `R6_CROSS_ENTITY_DUPLICATE`); R1–R5 findings get a **derived** deterministic neighborhood of the referenced invoice/vendor/contract records (`source: "derived"`).
```json
{"finding_id": "F-0007", "rule_id": "R6", "source": "stored",
 "nodes": [{"id": "Invoice:INV-9701", "label": "INV-9701", "type": "Invoice", "properties": {}, "highlight": true}],
 "edges": [{"source": "Vendor:V007", "target": "BankAccount:HDFC50100234567841", "type": "USES_BANK", "properties": {}}],
 "cypher_rule": "R6_CROSS_ENTITY_DUPLICATE", "summary": "..."}
```

### `GET /api/graph/entity/{entity_type}/{entity_id}?hops=2`
k-hop neighborhood (hops clamped to 1..3) around any whitelisted node: `Vendor`, `BankAccount`, `TaxIdentifier`, `Address`, `Approver`, `Contract`, `PurchaseOrder`, `Invoice`, `InvoiceLine`, `Payment`, `CreditNote`. Returns `{nodes, edges, cypher_rule: "ENTITY_NEIGHBORHOOD", summary}` with correct edge directions. `404` when the entity does not exist; `400` for unknown types.

### `POST /api/skills/inspect_entity_graph`
Read-only Agent Skill (same contract as the other skills): `{entity_type, entity_id, hops}` → deterministic neighborhood. Strictly parameterized; raw Cypher from untrusted input is impossible by construction.

## Conventions

- IDs are the stable text IDs from `docs/03_DATA_MODEL.md` (`F-0001`, `INV-8821`, …).
- Money is always `{amount_at_risk, currency}` pairs — never a bare float.
- Every mutating endpoint writes an audit row; no exceptions.
- The frontend talks **only** to these endpoints — keep this file in sync with code in the same PR.
