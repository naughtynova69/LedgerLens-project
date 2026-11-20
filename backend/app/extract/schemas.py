"""Structured-output schemas Gemini must conform to (docs/03 §3, docs/06 §3).

Extraction FAILS CLOSED: missing required fields quarantine the record with
needs_review instead of guessing silently.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class VendorExtracted(BaseModel):
    name: str | None = Field(default=None, description="Legal vendor name as printed")
    tax_id: str | None = Field(default=None, description="GSTIN / EIN / tax identifier")


class InvoiceHeaderExtracted(BaseModel):
    number: str | None = Field(default=None, description="Invoice number as printed")
    date: str | None = Field(default=None, description="Invoice date in YYYY-MM-DD format")
    currency: str | None = Field(default=None, description="ISO-4217 currency code")
    po_reference: str | None = Field(default=None, description="Referenced Purchase Order ID")
    payment_terms: str | None = Field(default=None, description="Payment terms, e.g. Net 30")


class InvoiceLineExtracted(BaseModel):
    item: str | None = Field(default=None, description="Line item description")
    quantity: float | None = Field(default=None, description="Billed unit quantity")
    unit_price: float | None = Field(default=None, description="Billed price per unit")
    tax_pct: float | None = Field(default=0.0, description="Tax percentage applied to line")
    line_total: float | None = Field(default=None, description="Line total inclusive of tax")


class InvoiceTotalsExtracted(BaseModel):
    subtotal: float | None = Field(default=None, description="Pre-tax subtotal")
    tax: float | None = Field(default=None, description="Total tax amount")
    grand_total: float | None = Field(default=None, description="Grand total payable")


class ExtractedInvoicePayload(BaseModel):
    vendor: VendorExtracted = Field(default_factory=VendorExtracted)
    invoice: InvoiceHeaderExtracted = Field(default_factory=InvoiceHeaderExtracted)
    lines: list[InvoiceLineExtracted] = Field(default_factory=list)
    totals: InvoiceTotalsExtracted = Field(default_factory=InvoiceTotalsExtracted)


class ContractHeaderExtracted(BaseModel):
    id: str | None = Field(default=None, description="Contract identifier")
    title: str | None = Field(default=None, description="Contract title")
    vendor_name: str | None = Field(default=None, description="Vendor legal name")
    start_date: str | None = Field(default=None, description="Start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="End date YYYY-MM-DD")
    status: str | None = Field(default="active", description="active | cancelled | terminated")


class ContractLineExtracted(BaseModel):
    item: str | None = Field(default=None, description="Contracted item or service")
    unit_price: float | None = Field(default=None, description="Negotiated unit price")
    currency: str | None = Field(default=None, description="ISO-4217 currency code")
    discount_pct: float | None = Field(default=0.0, description="Contracted discount percentage")
    payment_terms: str | None = Field(default=None, description="Agreed payment terms")
    tax_pct: float | None = Field(default=0.0, description="Contracted tax percentage")


class ExtractedContractPayload(BaseModel):
    contract: ContractHeaderExtracted = Field(default_factory=ContractHeaderExtracted)
    lines: list[ContractLineExtracted] = Field(default_factory=list)


class POHeaderExtracted(BaseModel):
    po_id: str | None = Field(default=None, description="Purchase order ID")
    vendor_name: str | None = Field(default=None, description="Vendor legal name")
    order_date: str | None = Field(default=None, description="Order date YYYY-MM-DD")
    expected_delivery: str | None = Field(default=None, description="Expected delivery YYYY-MM-DD")
    status: str | None = Field(default="open", description="open | delivered | cancelled")


class POLineExtracted(BaseModel):
    item: str | None = Field(default=None, description="Ordered item")
    quantity: float | None = Field(default=None, description="Authorized quantity")
    unit_price: float | None = Field(default=None, description="Authorized unit price")
    currency: str | None = Field(default=None, description="ISO-4217 currency code")


class ExtractedPOPayload(BaseModel):
    purchase_order: POHeaderExtracted = Field(default_factory=POHeaderExtracted)
    lines: list[POLineExtracted] = Field(default_factory=list)


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
