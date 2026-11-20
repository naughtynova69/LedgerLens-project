import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { CopilotDrawer } from "../components/CopilotDrawer";
import { Navbar } from "../components/Navbar";
import { api } from "../api";

vi.mock("../api", () => ({
  api: {
    askCopilot: vi.fn(),
    getExportCsvUrl: vi.fn(() => "/api/export/findings.csv"),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("CopilotDrawer", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <CopilotDrawer isOpen={false} onClose={vi.fn()} activeWorkspaceId="ws-acme" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("submits a question to api.askCopilot and renders grounded answer, mode, and citations", async () => {
    api.askCopilot.mockResolvedValueOnce({
      answer: "Total exposure across 2 open findings is INR 14,500.",
      mode: "gemini",
      workspace_id: "ws-acme",
      citations: [
        {
          finding_id: "FND-101",
          rule_id: "R1",
          amount_at_risk: 14500,
          currency: "INR",
          proof_trail: "Invoice INV-88 billed 14,500 above PO baseline.",
        },
      ],
    });

    render(
      <CopilotDrawer isOpen={true} onClose={vi.fn()} activeWorkspaceId="ws-acme" />
    );

    const input = screen.getByLabelText("Ask CFO Copilot");
    fireEvent.change(input, { target: { value: "What is our total exposure?" } });
    fireEvent.click(screen.getByRole("button", { name: /Ask/i }));

    await waitFor(() => {
      expect(api.askCopilot).toHaveBeenCalledWith(
        "What is our total exposure?",
        "ws-acme"
      );
    });

    expect(
      await screen.findByText("Total exposure across 2 open findings is INR 14,500.")
    ).toBeInTheDocument();
    expect(screen.getByText("gemini")).toBeInTheDocument();
    expect(screen.getByText("FND-101")).toBeInTheDocument();
    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(
      screen.getByText("Invoice INV-88 billed 14,500 above PO baseline.")
    ).toBeInTheDocument();
  });

  it("displays an error alert when api.askCopilot rejects", async () => {
    api.askCopilot.mockRejectedValueOnce(new Error("Copilot service unavailable"));

    render(
      <CopilotDrawer isOpen={true} onClose={vi.fn()} activeWorkspaceId="default" />
    );

    const input = screen.getByLabelText("Ask CFO Copilot");
    fireEvent.change(input, { target: { value: "Show top anomalies" } });
    fireEvent.click(screen.getByRole("button", { name: /Ask/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Copilot service unavailable");
  });
});

describe("Navbar CFO Copilot trigger", () => {
  it("calls onOpenCopilot when the CFO Copilot button is clicked", () => {
    const onOpenCopilot = vi.fn();
    render(
      <Navbar
        activeTab="exceptions"
        setActiveTab={vi.fn()}
        stats={{ by_status: { open: 2 } }}
        isOnline={true}
        onSeedDemo={vi.fn()}
        onOpenUploadModal={vi.fn()}
        onOpenMemoModal={vi.fn()}
        onOpenCopilot={onOpenCopilot}
        loadingAction={false}
        workspaces={[{ id: "default", name: "Default" }]}
        activeWorkspaceId="default"
        onChangeWorkspace={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /CFO Copilot/i }));
    expect(onOpenCopilot).toHaveBeenCalledTimes(1);
  });
});
