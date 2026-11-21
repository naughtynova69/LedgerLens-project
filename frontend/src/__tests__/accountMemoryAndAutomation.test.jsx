import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { AccountMemoryProvider } from "../context/AccountMemoryContext";
import { Navbar } from "../components/Navbar";
import { UploadModal } from "../components/UploadModal";
import { CopilotDrawer } from "../components/CopilotDrawer";
import { api } from "../api";

vi.mock("../api", () => ({
  api: {
    getAccountMemory: vi.fn(),
    putAccountMemory: vi.fn(),
    uploadDocument: vi.fn(),
    runExtract: vi.fn(),
    runDetect: vi.fn(),
    askCopilot: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  api.getAccountMemory.mockRejectedValue(new Error("404"));
  api.putAccountMemory.mockResolvedValue({ ok: true });
});

afterEach(() => {
  cleanup();
});

describe("Navbar Sandbox / Tools menu", () => {
  it("houses Seed Demo Dataset and Demo Guide inside Sandbox / Tools menu", () => {
    const onSeedDemo = vi.fn();
    const onOpenDemoGuide = vi.fn();

    render(
      <AccountMemoryProvider>
        <Navbar
          activeTab="exceptions"
          setActiveTab={vi.fn()}
          stats={{ by_status: { open: 1 } }}
          isOnline={true}
          onSeedDemo={onSeedDemo}
          onOpenUploadModal={vi.fn()}
          onOpenMemoModal={vi.fn()}
          onOpenCopilot={vi.fn()}
          onOpenDemoGuide={onOpenDemoGuide}
          loadingAction={false}
          workspaces={[{ id: "default", name: "Default" }]}
          activeWorkspaceId="default"
          onChangeWorkspace={vi.fn()}
        />
      </AccountMemoryProvider>
    );

    expect(screen.queryByRole("menuitem", { name: /Seed Demo Dataset/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Sandbox \/ Tools/i }));

    const seedItem = screen.getByRole("menuitem", { name: /Seed Demo Dataset/i });
    const guideItem = screen.getByRole("menuitem", { name: /Demo Guide/i });
    expect(seedItem).toBeInTheDocument();
    expect(guideItem).toBeInTheDocument();

    fireEvent.click(seedItem);
    expect(onSeedDemo).toHaveBeenCalledTimes(1);
  });
});

describe("UploadModal full automation", () => {
  it("runs automated Upload -> Extract -> Detect -> Explain via auto_run=true in one click", async () => {
    api.uploadDocument.mockResolvedValueOnce({
      batch_id: "batch-auto-1",
      auto_run: true,
      extract: { rows_extracted: 12, model: "deterministic" },
      detect: { findings_created: 3 },
    });

    const onPipelineComplete = vi.fn();
    render(
      <UploadModal
        isOpen={true}
        onClose={vi.fn()}
        onPipelineComplete={onPipelineComplete}
      />
    );

    const fileInput = document.querySelector('input[type="file"]');
    const file = new File(["invoice_number,amount\nINV-1,100"], "invoices.csv", {
      type: "text/csv",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByRole("button", { name: /Upload & Run Full Audit/i }));

    await waitFor(() => {
      expect(api.uploadDocument).toHaveBeenCalledWith("invoices", file, true);
    });

    expect(
      await screen.findByText(/Batch batch-auto-1 complete \(12 rows via deterministic, 3 findings\)/i)
    ).toBeInTheDocument();
    expect(api.runExtract).not.toHaveBeenCalled();
    expect(api.runDetect).not.toHaveBeenCalled();
    expect(onPipelineComplete).toHaveBeenCalledTimes(1);
  });
});

describe("CopilotDrawer with AccountMemory & page/finding context", () => {
  it("passes currentPage and selectedFinding context and persists history", async () => {
    api.askCopilot.mockResolvedValueOnce({
      answer: "FND-202 is a duplicate invoice worth INR 25,000.",
      mode: "deterministic",
      citations: [{ finding_id: "FND-202", rule_id: "R1", amount_at_risk: 25000, currency: "INR" }],
    });

    const { rerender } = render(
      <AccountMemoryProvider>
        <CopilotDrawer
          isOpen={true}
          onClose={vi.fn()}
          activeWorkspaceId="ws-fin"
          currentPage="exceptions"
          selectedFinding={{
            finding_id: "FND-202",
            rule_id: "R1",
            title: "Duplicate Invoice",
            amount_at_risk: 25000,
            currency: "INR",
            status: "open",
          }}
        />
      </AccountMemoryProvider>
    );

    const input = screen.getByLabelText("Ask CFO Copilot");
    fireEvent.change(input, { target: { value: "Explain this finding" } });
    fireEvent.click(screen.getByRole("button", { name: /Ask/i }));

    await waitFor(() => {
      expect(api.askCopilot).toHaveBeenCalledWith(
        "Explain this finding",
        "ws-fin",
        expect.objectContaining({
          currentPage: "exceptions",
          selectedFindingId: "FND-202",
        })
      );
    });

    expect(
      await screen.findByText("FND-202 is a duplicate invoice worth INR 25,000.")
    ).toBeInTheDocument();

    // Close and reopen drawer; history remains persisted in AccountMemory
    rerender(
      <AccountMemoryProvider>
        <CopilotDrawer
          isOpen={false}
          onClose={vi.fn()}
          activeWorkspaceId="ws-fin"
          currentPage="exceptions"
        />
      </AccountMemoryProvider>
    );
    rerender(
      <AccountMemoryProvider>
        <CopilotDrawer
          isOpen={true}
          onClose={vi.fn()}
          activeWorkspaceId="ws-fin"
          currentPage="exceptions"
        />
      </AccountMemoryProvider>
    );

    expect(
      screen.getByText("FND-202 is a duplicate invoice worth INR 25,000.")
    ).toBeInTheDocument();
  });
});
