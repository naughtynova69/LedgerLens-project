-- LedgerLens MVP schema (SQLite). Column dictionaries: docs/03_DATA_MODEL.md
-- Swapping to Cloud SQL later is a driver change, not a schema rewrite.

CREATE TABLE IF NOT EXISTS vendors (
    vendor_id        TEXT PRIMARY KEY,
    vendor_name      TEXT NOT NULL,
    tax_id           TEXT,
    default_currency TEXT NOT NULL DEFAULT 'INR',
    status           TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id           TEXT NOT NULL,
    vendor_id             TEXT NOT NULL REFERENCES vendors(vendor_id),
    item                  TEXT NOT NULL,
    contracted_unit_price REAL NOT NULL,
    currency              TEXT NOT NULL,
    discount_pct          REAL NOT NULL DEFAULT 0,
    payment_terms         TEXT,
    tax_pct               REAL NOT NULL DEFAULT 0,
    start_date            TEXT,
    end_date              TEXT,
    status                TEXT NOT NULL DEFAULT 'active',
    workspace_id          TEXT NOT NULL DEFAULT 'default',
    PRIMARY KEY (contract_id, item)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id             TEXT NOT NULL,
    po_line           INTEGER NOT NULL DEFAULT 1,
    vendor_id         TEXT NOT NULL REFERENCES vendors(vendor_id),
    item              TEXT NOT NULL,
    quantity          REAL NOT NULL,
    unit_price        REAL NOT NULL,
    currency          TEXT NOT NULL,
    order_date        TEXT,
    expected_delivery TEXT,
    status            TEXT NOT NULL DEFAULT 'open',
    workspace_id      TEXT NOT NULL DEFAULT 'default',
    PRIMARY KEY (po_id, po_line)
);

-- One row per invoice LINE (header fields repeat).
CREATE TABLE IF NOT EXISTS invoices (
    invoice_number TEXT NOT NULL,
    vendor_id      TEXT NOT NULL REFERENCES vendors(vendor_id),
    invoice_date   TEXT,
    po_id          TEXT,
    line_no        INTEGER NOT NULL DEFAULT 1,
    item           TEXT NOT NULL,
    quantity       REAL NOT NULL,
    unit_price     REAL NOT NULL,
    currency       TEXT NOT NULL,
    tax_pct        REAL NOT NULL DEFAULT 0,
    line_total     REAL NOT NULL,
    source_file    TEXT,
    status         TEXT NOT NULL DEFAULT 'unpaid',
    workspace_id   TEXT NOT NULL DEFAULT 'default',
    PRIMARY KEY (invoice_number, line_no)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id    TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL,
    amount        REAL NOT NULL,
    currency      TEXT NOT NULL,
    fx_rate_to_inr REAL NOT NULL DEFAULT 1.0,
    payment_date  TEXT,
    status        TEXT NOT NULL DEFAULT 'settled',
    workspace_id  TEXT NOT NULL DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id     TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    stored_path  TEXT,
    rows_detected INTEGER DEFAULT 0,
    state        TEXT NOT NULL DEFAULT 'uploaded',
    workspace_id TEXT NOT NULL DEFAULT 'default',
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Written by the detect stage. evidence/entity_refs/explanation are JSON text.
CREATE TABLE IF NOT EXISTS findings (
    finding_id     TEXT PRIMARY KEY,
    rule_id        TEXT NOT NULL,
    title          TEXT NOT NULL,
    severity       TEXT NOT NULL,
    amount_at_risk REAL NOT NULL DEFAULT 0,
    currency       TEXT NOT NULL DEFAULT 'INR',
    status         TEXT NOT NULL DEFAULT 'open',
    entity_refs    TEXT NOT NULL DEFAULT '{}',
    evidence       TEXT NOT NULL DEFAULT '[]',
    confidence     REAL NOT NULL DEFAULT 0,
    summary            TEXT DEFAULT '',
    explanation        TEXT,
    recommended_action TEXT NOT NULL DEFAULT '',
    proof_trail        TEXT NOT NULL DEFAULT '{}',
    workspace_id       TEXT NOT NULL DEFAULT 'default',
    created_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS decisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL REFERENCES findings(finding_id),
    action     TEXT NOT NULL,
    reviewer   TEXT NOT NULL,
    note       TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT DEFAULT (datetime('now')),
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    detail      TEXT DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT 'default'
);
