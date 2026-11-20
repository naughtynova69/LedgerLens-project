"""Typed LadybugDB property graph schema (master-prompt §3).

LadybugDB enforces a strict pre-defined property graph schema: every node table
requires a PRIMARY KEY and every relationship table declares ``FROM <Node> TO
<Node>``. All DDL is idempotent (``IF NOT EXISTS``) so initialization can run on
every startup and in every pytest run without side effects.
"""
from __future__ import annotations

from .client import GraphClient

NODE_TABLE_DDL: list[str] = [
    """CREATE NODE TABLE IF NOT EXISTS Vendor(
    vendor_id STRING PRIMARY KEY,
    name STRING,
    normalized_name STRING,
    email_domain STRING,
    phone_normalized STRING,
    status STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS BankAccount(
    account_key STRING PRIMARY KEY,
    masked_account STRING,
    bank_code STRING,
    currency STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS TaxIdentifier(
    tax_id STRING PRIMARY KEY,
    id_type STRING,
    country STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS Address(
    address_hash STRING PRIMARY KEY,
    normalized_address STRING,
    city STRING,
    country STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS Approver(
    approver_id STRING PRIMARY KEY,
    name STRING,
    email STRING,
    phone_normalized STRING,
    address_hash STRING,
    approval_limit DOUBLE
);""",
    """CREATE NODE TABLE IF NOT EXISTS Contract(
    contract_id STRING PRIMARY KEY,
    vendor_id STRING,
    effective_date STRING,
    expiry_date STRING,
    status STRING,
    unit_rate DOUBLE,
    currency STRING,
    item_key STRING,
    version INT64
);""",
]

REL_TABLE_DDL: list[str] = [
    "CREATE REL TABLE IF NOT EXISTS USES_BANK(FROM Vendor TO BankAccount, first_seen STRING);",
    "CREATE REL TABLE IF NOT EXISTS HAS_TAX_ID(FROM Vendor TO TaxIdentifier);",
    "CREATE REL TABLE IF NOT EXISTS LOCATED_AT(FROM Vendor TO Address);",
    "CREATE REL TABLE IF NOT EXISTS ISSUED_BY(FROM Invoice TO Vendor);",
    "CREATE REL TABLE IF NOT EXISTS HAS_LINE(FROM Invoice TO InvoiceLine);",
    "CREATE REL TABLE IF NOT EXISTS BILLED_UNDER_PO(FROM Invoice TO PurchaseOrder);",
    "CREATE REL TABLE IF NOT EXISTS GOVERNED_BY(FROM Invoice TO Contract);",
    "CREATE REL TABLE IF NOT EXISTS AMENDS(FROM Contract TO Contract, amendment_date STRING, rate_delta DOUBLE);",
    "CREATE REL TABLE IF NOT EXISTS SETTLED_BY(FROM Invoice TO Payment);",
    "CREATE REL TABLE IF NOT EXISTS PAID_TO_ACCOUNT(FROM Payment TO BankAccount);",
    "CREATE REL TABLE IF NOT EXISTS ISSUED_CREDIT(FROM Vendor TO CreditNote);",
    "CREATE REL TABLE IF NOT EXISTS APPLIED_TO_INVOICE(FROM CreditNote TO Invoice, applied_amount DOUBLE);",
    "CREATE REL TABLE IF NOT EXISTS APPROVED_INVOICE(FROM Approver TO Invoice, approved_at STRING);",
    "CREATE REL TABLE IF NOT EXISTS APPROVER_USES_BANK(FROM Approver TO BankAccount);",
    "CREATE REL TABLE IF NOT EXISTS APPROVER_LOCATED_AT(FROM Approver TO Address);",
]

# Node tables that reference rel tables in their DDL ordering (Invoice /
# InvoiceLine / Payment / CreditNote are pure node tables but must exist before
# the rel DDL runs; they are appended after Vendor-family nodes).
NODE_TABLE_DDL_TAIL: list[str] = [
    """CREATE NODE TABLE IF NOT EXISTS PurchaseOrder(
    po_id STRING PRIMARY KEY,
    vendor_id STRING,
    item_key STRING,
    ordered_qty DOUBLE,
    unit_price DOUBLE,
    total_amount DOUBLE,
    currency STRING,
    status STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS Invoice(
    invoice_id STRING PRIMARY KEY,
    batch_id STRING,
    invoice_number STRING,
    vendor_id STRING,
    invoice_date STRING,
    grand_total DOUBLE,
    currency STRING,
    status STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS InvoiceLine(
    line_id STRING PRIMARY KEY,
    invoice_id STRING,
    item_key STRING,
    description STRING,
    quantity DOUBLE,
    unit_price DOUBLE,
    line_total DOUBLE
);""",
    """CREATE NODE TABLE IF NOT EXISTS Payment(
    payment_id STRING PRIMARY KEY,
    invoice_id STRING,
    paid_date STRING,
    amount DOUBLE,
    currency STRING,
    account_key STRING
);""",
    """CREATE NODE TABLE IF NOT EXISTS CreditNote(
    credit_note_id STRING PRIMARY KEY,
    vendor_id STRING,
    issue_date STRING,
    amount DOUBLE,
    currency STRING,
    applied_status STRING
);""",
]

ALL_DDL: list[str] = NODE_TABLE_DDL + NODE_TABLE_DDL_TAIL + REL_TABLE_DDL


def initialize_schema(client: GraphClient) -> None:
    """Run all idempotent DDL statements in dependency order."""
    for ddl in ALL_DDL:
        client.execute_write(ddl)
