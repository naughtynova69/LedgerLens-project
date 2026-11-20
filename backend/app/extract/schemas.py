"""Structured-output schemas Gemini must conform to (docs/03 §3, docs/06 §3).

Extraction FAILS CLOSED: missing required fields quarantine the record with
needs_review instead of guessing silently.
"""

INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "nullable": True},
                "tax_id": {"type": "string", "nullable": True},
            },
        },
        "invoice": {
            "type": "object",
            "properties": {
                "number": {"type": "string", "nullable": True},
                "date": {"type": "string", "nullable": True},
                "currency": {"type": "string", "nullable": True},
                "po_reference": {"type": "string", "nullable": True},
                "payment_terms": {"type": "string", "nullable": True},
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "nullable": True},
                    "quantity": {"type": "number", "nullable": True},
                    "unit_price": {"type": "number", "nullable": True},
                    "tax_pct": {"type": "number", "nullable": True},
                    "line_total": {"type": "number", "nullable": True},
                },
            },
        },
        "totals": {
            "type": "object",
            "properties": {
                "subtotal": {"type": "number", "nullable": True},
                "tax": {"type": "number", "nullable": True},
                "grand_total": {"type": "number", "nullable": True},
            },
        },
    },
}

CONTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "contract": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "nullable": True},
                "title": {"type": "string", "nullable": True},
                "vendor_name": {"type": "string", "nullable": True},
                "start_date": {"type": "string", "nullable": True},
                "end_date": {"type": "string", "nullable": True},
                "status": {"type": "string", "nullable": True},
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "nullable": True},
                    "unit_price": {"type": "number", "nullable": True},
                    "currency": {"type": "string", "nullable": True},
                    "discount_pct": {"type": "number", "nullable": True},
                    "payment_terms": {"type": "string", "nullable": True},
                    "tax_pct": {"type": "number", "nullable": True},
                },
            },
        },
    },
}
