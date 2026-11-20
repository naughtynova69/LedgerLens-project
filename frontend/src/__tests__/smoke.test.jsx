import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { NeedsReviewDrawer } from "../components/NeedsReviewDrawer";
import { PdfEvidencePreview } from "../components/PdfEvidencePreview";
import { WorkspaceSwitcher } from "../components/WorkspaceSwitcher";

afterEach(() => {
  cleanup();
});

describe("NeedsReviewDrawer", () => {
  const sampleRecords = [
    {
      id: "rec-1",
      vendor_id: "V-101",
      invoice_number: "INV-9001",
      item: "Cloud Compute",
      quantity: 10,
      unit_price: 120,
      tax_pct: 18,
      line_total: 1416,
      reason: "Tax mismatch",
    },
  ];

  it("renders nothing when closed", () => {
    const { container } = render(
      <NeedsReviewDrawer
        isOpen={false}
        onClose={vi.fn()}
        batch={{ batch_id: "batch-1" }}
        records={sampleRecords}
        onSaveAndRedetect={vi.fn()}
        saving={false}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("allows editing quarantined fields and submitting Save & Re-Run Detection", () => {
    const onSaveAndRedetect = vi.fn();
    render(
      <NeedsReviewDrawer
        isOpen={true}
        onClose={vi.fn()}
        batch={{ batch_id: "batch-1" }}
        records={sampleRecords}
        onSaveAndRedetect={onSaveAndRedetect}
        saving={false}
      />
    );

    expect(screen.getByText("Quarantined Invoice Lines")).toBeInTheDocument();
    expect(screen.getByText("Tax mismatch")).toBeInTheDocument();

    const invoiceInput = screen.getByLabelText("Invoice Number");
    const itemInput = screen.getByLabelText("Item Description");
    const qtyInput = screen.getByLabelText("Quantity");
    const unitPriceInput = screen.getByLabelText("Unit Price");
    const taxInput = screen.getByLabelText("Tax %");
    const totalInput = screen.getByLabelText("Line Total");

    fireEvent.change(invoiceInput, { target: { value: "INV-9001-FIXED" } });
    fireEvent.change(itemInput, { target: { value: "Cloud Compute Pro" } });
    fireEvent.change(qtyInput, { target: { value: "12" } });
    fireEvent.change(unitPriceInput, { target: { value: "125" } });
    fireEvent.change(taxInput, { target: { value: "18" } });
    fireEvent.change(totalInput, { target: { value: "1770" } });

    fireEvent.click(screen.getByRole("button", { name: /Save & Re-Run Detection/i }));

    expect(onSaveAndRedetect).toHaveBeenCalledTimes(1);
    const submitted = onSaveAndRedetect.mock.calls[0][0];
    expect(submitted[0]).toMatchObject({
      invoice_number: "INV-9001-FIXED",
      item: "Cloud Compute Pro",
      quantity: 12,
      unit_price: 125,
      tax_pct: 18,
      line_total: 1770,
    });
  });
});

describe("PdfEvidencePreview", () => {
  it("renders an iframe for PDF batches", () => {
    render(
      <PdfEvidencePreview
        batchId="batch-pdf-1"
        fileName="vendor_invoice.pdf"
        mimeType="application/pdf"
      />
    );
    const iframe = screen.getByTitle("vendor_invoice.pdf");
    expect(iframe).toBeInTheDocument();
    expect(iframe).toHaveAttribute("src", "/api/batches/batch-pdf-1/file");
  });

  it("renders an img for image batches", () => {
    render(
      <PdfEvidencePreview
        batchId="batch-img-2"
        fileName="scan.png"
        mimeType="image/png"
      />
    );
    const img = screen.getByAltText("scan.png");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "/api/batches/batch-img-2/file");
  });

  it("renders a clean fallback for CSV or missing files", () => {
    const { rerender } = render(
      <PdfEvidencePreview
        batchId="batch-csv-3"
        fileName="invoices.csv"
        mimeType="text/csv"
      />
    );
    expect(screen.getByText(/Tabular CSV batch/i)).toBeInTheDocument();

    rerender(<PdfEvidencePreview batchId={null} fileName="" mimeType="" />);
    expect(screen.getByText(/No source document attached/i)).toBeInTheDocument();
  });
});

describe("WorkspaceSwitcher", () => {
  const workspaces = [
    { id: "ws-acme", name: "Acme Corp (FY26)" },
    { id: "ws-globex", name: "Globex Industries" },
  ];

  it("renders workspace options and triggers onChangeWorkspace", () => {
    const onChangeWorkspace = vi.fn();
    render(
      <WorkspaceSwitcher
        workspaces={workspaces}
        activeWorkspaceId="ws-acme"
        onChangeWorkspace={onChangeWorkspace}
      />
    );

    const select = screen.getByLabelText("Client workspace");
    expect(select).toHaveValue("ws-acme");
    expect(screen.getByRole("option", { name: "Acme Corp (FY26)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Globex Industries" })).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "ws-globex" } });
    expect(onChangeWorkspace).toHaveBeenCalledWith("ws-globex");
  });
});
