import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { AuditLogView } from "../views/AuditLogView";
import { api } from "../api";

vi.mock("../api", () => ({
  api: {
    verifyAuditChain: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuditLogView hash-chain verification", () => {
  const sampleLogs = [
    {
      id: 1,
      actor: "auditor",
      action: "approved",
      object_type: "finding",
      object_id: "F-101",
      detail: "Approved duplicate invoice finding",
      ts: "2026-11-20T10:00:00Z",
    },
  ];

  const sampleBatches = [
    {
      batch_id: "B-100",
      kind: "invoices",
      rows_detected: 25,
      state: "completed",
      created_at: "2026-11-20T09:55:00Z",
    },
  ];

  it("shows loading state and renders an emerald banner when the audit chain is valid", async () => {
    let resolveVerify;
    api.verifyAuditChain.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveVerify = resolve;
        })
    );

    render(
      <AuditLogView
        logs={sampleLogs}
        batches={sampleBatches}
        onSelectFinding={vi.fn()}
      />
    );

    const verifyButton = screen.getByRole("button", {
      name: /Verify Ledger Integrity/i,
    });
    fireEvent.click(verifyButton);

    expect(api.verifyAuditChain).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /Verifying\.\.\./i })).toBeDisabled();

    resolveVerify({
      valid: true,
      checked_entries: 42,
      head_hash: "a1b2c3d4e5f67890abcdef1234567890",
    });

    const statusBanner = await screen.findByRole("status");
    expect(statusBanner).toHaveClass("bg-emerald-50");
    expect(screen.getByText("Ledger Integrity Verified")).toBeInTheDocument();
    expect(statusBanner).toHaveTextContent("42");
    expect(statusBanner).toHaveTextContent("a1b2c3d4e5f6...");
  });

  it("renders a crimson banner with broken_at_id and reason when the audit chain is tampered", async () => {
    api.verifyAuditChain.mockResolvedValue({
      valid: false,
      checked_entries: 18,
      broken_at_id: 7,
      reason: "prev_hash mismatch at entry 7",
    });

    render(
      <AuditLogView
        logs={sampleLogs}
        batches={sampleBatches}
        onSelectFinding={vi.fn()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Verify Ledger Integrity/i })
    );

    const alertBanner = await screen.findByRole("alert");
    expect(alertBanner).toHaveClass("bg-rose-50");
    expect(screen.getByText("Ledger Integrity Compromised")).toBeInTheDocument();
    expect(alertBanner).toHaveTextContent("18");
    expect(alertBanner).toHaveTextContent("#7");
    expect(alertBanner).toHaveTextContent("prev_hash mismatch at entry 7");
  });

  it("renders an error banner when verifyAuditChain rejects", async () => {
    api.verifyAuditChain.mockRejectedValue(new Error("Network timeout"));

    render(
      <AuditLogView
        logs={sampleLogs}
        batches={sampleBatches}
        onSelectFinding={vi.fn()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Verify Ledger Integrity/i })
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Network timeout");
    });
    expect(screen.getByText("Verification Error")).toBeInTheDocument();
  });
});
