-- LedgerLens BigQuery Analytics Warehouse DDL (BigQuery Standard SQL).
-- Default dataset: ledgerlens_analytics (substitute ${BQ_DATASET} when templating).

CREATE SCHEMA IF NOT EXISTS ledgerlens_analytics;

CREATE TABLE IF NOT EXISTS ledgerlens_analytics.audited_invoices (
    invoice_number STRING NOT NULL,
    line_no        INT64 NOT NULL,
    vendor_id      STRING NOT NULL,
    vendor_name    STRING,
    invoice_date   STRING,
    po_id          STRING,
    item           STRING NOT NULL,
    quantity       FLOAT64 NOT NULL,
    unit_price     FLOAT64 NOT NULL,
    currency       STRING NOT NULL,
    tax_pct        FLOAT64 NOT NULL,
    line_total     FLOAT64 NOT NULL,
    fx_rate_to_inr FLOAT64 NOT NULL,
    line_total_inr FLOAT64 NOT NULL,
    source_file    STRING,
    status         STRING NOT NULL,
    synced_at      TIMESTAMP NOT NULL
)
PARTITION BY DATE(synced_at)
CLUSTER BY vendor_id, currency;

CREATE TABLE IF NOT EXISTS ledgerlens_analytics.audit_findings (
    finding_id         STRING NOT NULL,
    rule_id            STRING NOT NULL,
    title              STRING NOT NULL,
    severity           STRING NOT NULL,
    status             STRING NOT NULL,
    amount_at_risk     FLOAT64 NOT NULL,
    currency           STRING NOT NULL,
    fx_rate_to_inr     FLOAT64 NOT NULL,
    amount_at_risk_inr FLOAT64 NOT NULL,
    vendor_id          STRING,
    vendor_name        STRING,
    confidence         FLOAT64 NOT NULL,
    summary            STRING,
    recommended_action STRING,
    entity_refs        STRING,
    evidence           STRING,
    explanation        STRING,
    proof_trail        STRING,
    created_at         STRING,
    synced_at          TIMESTAMP NOT NULL
)
PARTITION BY DATE(synced_at)
CLUSTER BY rule_id, status, severity;

CREATE TABLE IF NOT EXISTS ledgerlens_analytics.audit_log_events (
    event_id    INT64 NOT NULL,
    ts          STRING,
    actor       STRING NOT NULL,
    action      STRING NOT NULL,
    object_type STRING NOT NULL,
    object_id   STRING NOT NULL,
    detail      STRING,
    synced_at   TIMESTAMP NOT NULL
)
PARTITION BY DATE(synced_at)
CLUSTER BY action, object_type;

-- Vendor leakage ranking across the latest synced snapshot of each finding.
CREATE OR REPLACE VIEW ledgerlens_analytics.v_vendor_leakage_ranking AS
WITH latest_findings AS (
    SELECT *
    FROM ledgerlens_analytics.audit_findings
    QUALIFY ROW_NUMBER() OVER (PARTITION BY finding_id ORDER BY synced_at DESC) = 1
)
SELECT
    COALESCE(vendor_id, 'UNKNOWN') AS vendor_id,
    COALESCE(ANY_VALUE(vendor_name), COALESCE(vendor_id, 'UNKNOWN')) AS vendor_name,
    COUNT(*) AS finding_count,
    ROUND(SUM(amount_at_risk_inr), 2) AS total_at_risk_inr,
    ROUND(SUM(IF(LOWER(status) = 'open', amount_at_risk_inr, 0.0)), 2) AS open_at_risk_inr,
    ROUND(SUM(IF(LOWER(status) IN ('rejected', 'recovery', 'recovered'), amount_at_risk_inr, 0.0)), 2) AS recovered_inr
FROM latest_findings
GROUP BY vendor_id
ORDER BY total_at_risk_inr DESC;

-- Rule-level exposure summary (R1-R5) across the latest synced snapshot.
CREATE OR REPLACE VIEW ledgerlens_analytics.v_rule_exposure_summary AS
WITH latest_findings AS (
    SELECT *
    FROM ledgerlens_analytics.audit_findings
    QUALIFY ROW_NUMBER() OVER (PARTITION BY finding_id ORDER BY synced_at DESC) = 1
)
SELECT
    rule_id,
    COUNT(*) AS finding_count,
    COUNTIF(LOWER(status) = 'open') AS open_count,
    COUNTIF(LOWER(status) IN ('rejected', 'recovery', 'recovered')) AS recovered_count,
    ROUND(SUM(amount_at_risk_inr), 2) AS total_at_risk_inr,
    ROUND(SUM(IF(LOWER(status) = 'open', amount_at_risk_inr, 0.0)), 2) AS open_at_risk_inr,
    ROUND(SUM(IF(LOWER(status) IN ('rejected', 'recovery', 'recovered'), amount_at_risk_inr, 0.0)), 2) AS recovered_inr,
    ROUND(AVG(confidence), 4) AS avg_confidence
FROM latest_findings
GROUP BY rule_id
ORDER BY total_at_risk_inr DESC;

-- Executive recovery ROI summary across audited spend and findings.
CREATE OR REPLACE VIEW ledgerlens_analytics.v_recovery_roi AS
WITH latest_invoices AS (
    SELECT *
    FROM ledgerlens_analytics.audited_invoices
    QUALIFY ROW_NUMBER() OVER (PARTITION BY invoice_number, line_no ORDER BY synced_at DESC) = 1
),
latest_findings AS (
    SELECT *
    FROM ledgerlens_analytics.audit_findings
    QUALIFY ROW_NUMBER() OVER (PARTITION BY finding_id ORDER BY synced_at DESC) = 1
),
spend_agg AS (
    SELECT COALESCE(SUM(line_total_inr), 0.0) AS total_audited_spend_inr
    FROM latest_invoices
),
findings_agg AS (
    SELECT
        COUNT(*) AS total_findings,
        COALESCE(SUM(amount_at_risk_inr), 0.0) AS total_at_risk_inr,
        COALESCE(SUM(IF(LOWER(status) = 'open', amount_at_risk_inr, 0.0)), 0.0) AS open_at_risk_inr,
        COALESCE(SUM(IF(LOWER(status) IN ('rejected', 'recovery', 'recovered'), amount_at_risk_inr, 0.0)), 0.0) AS recovered_inr
    FROM latest_findings
)
SELECT
    ROUND(spend_agg.total_audited_spend_inr, 2) AS total_audited_spend_inr,
    findings_agg.total_findings,
    ROUND(findings_agg.total_at_risk_inr, 2) AS total_at_risk_inr,
    ROUND(findings_agg.open_at_risk_inr, 2) AS open_at_risk_inr,
    ROUND(findings_agg.recovered_inr, 2) AS recovered_inr,
    ROUND(COALESCE(SAFE_DIVIDE(findings_agg.total_at_risk_inr, spend_agg.total_audited_spend_inr) * 100.0, 0.0), 2) AS leakage_pct_of_spend,
    ROUND(COALESCE(SAFE_DIVIDE(findings_agg.recovered_inr, findings_agg.total_at_risk_inr) * 100.0, 0.0), 2) AS recovery_rate_pct
FROM spend_agg
CROSS JOIN findings_agg;
