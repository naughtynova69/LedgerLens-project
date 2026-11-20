import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "./components/Navbar";
import { Toast } from "./components/Toast";
import { Modal } from "./components/Modal";
import { UploadModal } from "./components/UploadModal";
import { NeedsReviewDrawer } from "./components/NeedsReviewDrawer";
import { CopilotDrawer } from "./components/CopilotDrawer";
import { FindingsView } from "./views/FindingsView";
import { AuditLogView } from "./views/AuditLogView";
import { RulesView } from "./views/RulesView";
import { CloudIntegrationsView } from "./views/CloudIntegrationsView";
import { MemoView } from "./views/MemoView";
import { api } from "./api";

export function App() {
  const [activeTab, setActiveTab] = useState("exceptions");
  const [stats, setStats] = useState(null);
  const [findings, setFindings] = useState([]);
  const [batches, setBatches] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [memoData, setMemoData] = useState(null);
  const [executiveAnalytics, setExecutiveAnalytics] = useState(null);
  const [isOnline, setIsOnline] = useState(true);
  const [loadingAction, setLoadingAction] = useState(false);
  const [toast, setToast] = useState(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [memoModalOpen, setMemoModalOpen] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState("default");
  const [reviewBatch, setReviewBatch] = useState(null);
  const [reviewRecords, setReviewRecords] = useState([]);
  const [savingReview, setSavingReview] = useState(false);

  // Split-View Selection
  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [selectedFindingDetail, setSelectedFindingDetail] = useState(null);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  const showToast = useCallback((message, type = "info", title = "") => {
    setToast({ message, type, title });
    setTimeout(() => {
      setToast((curr) => (curr?.message === message ? null : curr));
    }, 4500);
  }, []);

  const handleSelectFinding = useCallback(
    async (findingId) => {
      if (!findingId) return;
      setSelectedFindingId(findingId);
      try {
        const detail = await api.getFinding(findingId);
        setSelectedFindingDetail(detail);
      } catch (err) {
        showToast(err.message, "error", "Failed to Load Proof Trail");
      }
    },
    [showToast]
  );

  const loadData = useCallback(async () => {
    try {
      const [h, s, f, b, m, l, exec, ws] = await Promise.all([
        api.getHealth().catch(() => ({ status: "offline" })),
        api.getStats().catch(() => null),
        api.getFindings().catch(() => []),
        api.getBatches().catch(() => []),
        api.getMemo().catch(() => null),
        api.getAuditLog().catch(() => []),
        api.getExecutiveAnalytics().catch(() => null),
        api.getWorkspaces().catch(() => []),
      ]);

      setIsOnline(h.status === "ok");
      if (s) setStats(s);
      if (f) {
        setFindings(f);
        if (f.length > 0 && !selectedFindingId) {
          handleSelectFinding(f[0].finding_id);
        }
      }
      if (b) setBatches(b);
      if (m) setMemoData(m);
      if (l) setAuditLogs(l);
      if (exec) setExecutiveAnalytics(exec);
      if (Array.isArray(ws) && ws.length > 0) {
        setWorkspaces(ws);
      }
    } catch {
      setIsOnline(false);
    }
  }, [selectedFindingId, handleSelectFinding]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleSeedDemo = async () => {
    setLoadingAction(true);
    try {
      const res = await api.seedSampleData();
      showToast(
        `Seeded sample dataset: ${res.findings_created} planted anomalies detected (₹${res.total_at_risk?.toLocaleString(
          "en-IN"
        )} at risk).`,
        "success",
        "Demo Dataset Loaded"
      );
      const freshFindings = await api.getFindings().catch(() => []);
      await loadData();
      if (freshFindings.length > 0) {
        await handleSelectFinding(freshFindings[0].finding_id);
      }
      setActiveTab("exceptions");
    } catch (err) {
      showToast(err.message, "error", "Seed Failed");
    } finally {
      setLoadingAction(false);
    }
  };

  const handleRunDetect = async () => {
    setLoadingAction(true);
    try {
      const res = await api.runGlobalDetect();
      showToast(
        `Deterministic R1–R5 rules evaluated: ${res.findings_created} active finding(s).`,
        "success",
        "Detection Complete"
      );
      await loadData();
    } catch (err) {
      showToast(err.message, "error", "Detection Failed");
    } finally {
      setLoadingAction(false);
    }
  };

  const handleMakeDecision = async (findingId, action, reviewer, note) => {
    setIsSubmittingDecision(true);
    try {
      const res = await api.postDecision(findingId, action, reviewer, note);
      showToast(
        `Finding ${findingId} marked "${res.status}". Audit log updated.`,
        "success",
        "Decision Recorded"
      );
      const updatedDetail = await api.getFinding(findingId);
      setSelectedFindingDetail(updatedDetail);
      await loadData();
    } catch (err) {
      showToast(err.message, "error", "Decision Failed");
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const handleBulkDecision = async (findingIds, action) => {
    setIsSubmittingDecision(true);
    try {
      const defaultNote =
        action === "recovery"
          ? "Bulk hold / recovery initiated via Exceptions workbench."
          : "Bulk approved as valid / false positive via Exceptions workbench.";
      const res = await api.postBulkDecision(
        findingIds,
        action,
        "Vijay (AP Lead)",
        defaultNote
      );
      showToast(
        `Updated ${res.updated_count} exception(s) to "${res.status}".`,
        "success",
        "Bulk Triage Complete"
      );
      if (selectedFindingId && findingIds.includes(selectedFindingId)) {
        const updatedDetail = await api.getFinding(selectedFindingId).catch(() => null);
        if (updatedDetail) setSelectedFindingDetail(updatedDetail);
      }
      await loadData();
    } catch (err) {
      showToast(err.message, "error", "Bulk Action Failed");
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const needsReviewBatches = (batches || []).filter(
    (b) => b.status === "needs_review"
  );

  const handleOpenReviewDrawer = (batch) => {
    setReviewBatch(batch);
    setReviewRecords(batch.needs_review_records || batch.records || []);
  };

  const handleSaveAndRedetect = async (updatedRecords) => {
    if (!reviewBatch?.batch_id) return;
    setSavingReview(true);
    try {
      await api.updateBatchRecords(reviewBatch.batch_id, {
        records: updatedRecords,
      });
      await api.runDetect(reviewBatch.batch_id);
      showToast(
        `Updated quarantined lines for ${reviewBatch.batch_id} and re-ran detection.`,
        "success",
        "Quarantine Resolved"
      );
      setReviewBatch(null);
      setReviewRecords([]);
      await loadData();
    } catch (err) {
      showToast(err.message, "error", "Failed to Update Quarantined Lines");
    } finally {
      setSavingReview(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#111827] flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        isOnline={isOnline}
        onSeedDemo={handleSeedDemo}
        onOpenUploadModal={() => setUploadModalOpen(true)}
        onOpenMemoModal={() => setMemoModalOpen(true)}
        onOpenCopilot={() => setCopilotOpen(true)}
        loadingAction={loadingAction}
        workspaces={workspaces}
        activeWorkspaceId={activeWorkspaceId}
        onChangeWorkspace={(wsId) => {
          setActiveWorkspaceId(wsId);
          showToast(`Switched workspace to ${wsId}.`, "info", "Workspace Changed");
        }}
      />

      {needsReviewBatches.length > 0 && (
        <div className="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-4">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
            <span>
              <span className="font-semibold">
                {needsReviewBatches.length}{" "}
                {needsReviewBatches.length === 1 ? "batch" : "batches"}
              </span>{" "}
              quarantined with <span className="font-mono">needs_review</span> invoice
              lines awaiting manual correction.
            </span>
            <button
              type="button"
              onClick={() => handleOpenReviewDrawer(needsReviewBatches[0])}
              className="px-2.5 py-1 rounded-md font-medium bg-white border border-amber-300 text-amber-900 hover:bg-amber-100/60 transition-colors"
            >
              Review &amp; Fix Lines
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === "exceptions" && (
          <FindingsView
            findings={findings}
            stats={stats}
            executiveAnalytics={executiveAnalytics}
            selectedFindingId={selectedFindingId}
            selectedFindingDetail={selectedFindingDetail}
            onSelectFinding={handleSelectFinding}
            onMakeDecision={handleMakeDecision}
            onBulkDecision={handleBulkDecision}
            isSubmittingDecision={isSubmittingDecision}
            onSeedDemo={handleSeedDemo}
            loadingAction={loadingAction}
            onToast={showToast}
          />
        )}

        {activeTab === "activity" && (
          <AuditLogView
            logs={auditLogs}
            batches={batches}
            onSelectFinding={(id) => {
              handleSelectFinding(id);
              setActiveTab("exceptions");
            }}
            onOpenUploadModal={() => setUploadModalOpen(true)}
            onRunDetect={handleRunDetect}
            loadingAction={loadingAction}
          />
        )}

        {activeTab === "rules" && <RulesView />}

        {activeTab === "cloud" && (
          <CloudIntegrationsView
            executiveAnalytics={executiveAnalytics}
            onRefreshAnalytics={loadData}
            onToast={showToast}
          />
        )}
      </main>

      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onPipelineComplete={async () => {
          await loadData();
          setActiveTab("exceptions");
        }}
      />

      <NeedsReviewDrawer
        isOpen={Boolean(reviewBatch)}
        onClose={() => {
          setReviewBatch(null);
          setReviewRecords([]);
        }}
        batch={reviewBatch}
        records={reviewRecords}
        onSaveAndRedetect={handleSaveAndRedetect}
        saving={savingReview}
      />

      <CopilotDrawer
        isOpen={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        activeWorkspaceId={activeWorkspaceId}
      />

      <Modal
        isOpen={memoModalOpen}
        onClose={() => setMemoModalOpen(false)}
        title="CFO Audit Memo"
        maxWidth="max-w-4xl"
      >
        <MemoView
          memoData={memoData}
          onRefreshMemo={loadData}
          onCopy={() => showToast("Audit memo copied to clipboard.", "success")}
        />
      </Modal>

      <Toast toast={toast} onClose={() => setToast(null)} />

      <footer className="border-t border-gray-200 bg-white py-3 text-xs text-[#6B7280]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>LedgerLens · Explainable AI Money-Leak Auditor</span>
          <span className="font-mono text-[11px]">
            Deterministic Rules R1–R10 (LadybugDB Graph) · Gemini 3.8 Vision Flash
          </span>
        </div>
      </footer>
    </div>
  );
}
