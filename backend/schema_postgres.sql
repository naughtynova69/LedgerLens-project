-- LedgerLens PostgreSQL / AlloyDB production schema.
-- Aligned 100% with backend/schema.sql (SQLite MVP schema) plus policy_settings.
--
-- Note: In AlloyDB / PostgreSQL, enable pgvector for semantic SKU matching:
-- CREATE EXTENSION IF NOT EXISTS vector;

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
    contracted_unit_price NUMERIC(14, 2) NOT NULL,
    currency              TEXT NOT NULL,
    discount_pct          DOUBLE PRECISION NOT NULL DEFAULT 0,
    payment_terms         TEXT,
    tax_pct               DOUBLE PRECISION NOT NULL DEFAULT 0,
    start_date            TEXT,
    end_date              TEXT,
    status                TEXT NOT NULL DEFAULT 'active',
    PRIMARY KEY (contract_id, item)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id             TEXT NOT NULL,
    po_line           INTEGER NOT NULL DEFAULT 1,
    vendor_id         TEXT NOT NULL REFERENCES vendors(vendor_id),
    item              TEXT NOT NULL,
    quantity          DOUBLE PRECISION NOT NULL,
    unit_price        NUMERIC(14, 2) NOT NULL,
    currency          TEXT NOT NULL,
    order_date        TEXT,
    expected_delivery TEXT,
    status            TEXT NOT NULL DEFAULT 'open',
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
    quantity       DOUBLE PRECISION NOT NULL,
    unit_price     NUMERIC(14, 2) NOT NULL,
    currency       TEXT NOT NULL,
    tax_pct        DOUBLE PRECISION NOT NULL DEFAULT 0,
    line_total     NUMERIC(14, 2) NOT NULL,
    source_file    TEXT,
    status         TEXT NOT NULL DEFAULT 'unpaid',
    PRIMARY KEY (invoice_number, line_no)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id     TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL,
    amount         NUMERIC(14, 2) NOT NULL,
    currency       TEXT NOT NULL,
    fx_rate_to_inr DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    payment_date   TEXT,
    status         TEXT NOT NULL DEFAULT 'settled'
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id      TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    stored_path   TEXT,
    rows_detected INTEGER DEFAULT 0,
    state         TEXT NOT NULL DEFAULT 'uploaded',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Written by the detect stage. entity_refs/evidence/explanation/proof_trail are JSONB.
CREATE TABLE IF NOT EXISTS findings (
    finding_id         TEXT PRIMARY KEY,
    rule_id            TEXT NOT NULL,
    title              TEXT NOT NULL,
    severity           TEXT NOT NULL,
    amount_at_risk     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency           TEXT NOT NULL DEFAULT 'INR',
    status             TEXT NOT NULL DEFAULT 'open',
    entity_refs        JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence           JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence         DOUBLE PRECISION NOT NULL DEFAULT 0,
    summary            TEXT DEFAULT '',
    explanation        JSONB,
    recommended_action TEXT NOT NULL DEFAULT '',
    proof_trail        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    id         BIGSERIAL PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES findings(finding_id),
    action     TEXT NOT NULL,
    reviewer   TEXT NOT NULL,
    note       TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ DEFAULT NOW(),
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    detail      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS policy_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Production B-tree indexes for LedgerLens query hot paths.
CREATE INDEX IF NOT EXISTS idx_invoices_vendor_date
    ON invoices (vendor_id, invoice_date);

CREATE INDEX IF NOT EXISTS idx_findings_status_rule_risk
    ON findings (status, rule_id, amount_at_risk DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_ts
    ON audit_log (ts DESC);
