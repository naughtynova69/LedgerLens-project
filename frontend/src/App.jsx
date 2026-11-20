import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "./components/Navbar";
import { Toast } from "./components/Toast";
import { UploadModal } from "./components/UploadModal";
import { DashboardView } from "./views/DashboardView";
import { FindingsView } from "./views/FindingsView";
import { UploadView } from "./views/UploadView";
import { MemoView } from "./views/MemoView";
import { RulesView } from "./views/RulesView";
import { AuditLogView } from "./views/AuditLogView";
import { api } from "./api";

export function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [findings, setFindings] = useState([]);
  const [batches, setBatches] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [memoData, setMemoData] = useState(null);
  const [isOnline, setIsOnline] = useState(true);
  const [loadingAction, setLoadingAction] = useState(false);
  const [toast, setToast] = useState(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  // Split-View Proof Trail Selection
  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [selectedFindingDetail, setSelectedFindingDetail] = useState(null);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  const showToast = (message, type = "info", title = "") => {
    setToast({ message, type, title });
    setTimeout(() => {
      setToast((curr) => (curr?.message === message ? null : curr));
    }, 4500);
  };

  const handleSelectFinding = useCallback(async (findingId) => {
    if (!findingId) return;
    setSelectedFindingId(findingId);
    try {
      const detail = await api.getFinding(findingId);
      setSelectedFindingDetail(detail);
    } catch (err) {
      showToast(err.message, "error", "Failed to Load Proof Trail");
    }
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [h, s, f, b, m, l] = await Promise.all([
        api.getHealth().catch(() => ({ status: "offline" })),
        api.getStats().catch(() => null),
        api.getFindings().catch(() => []),
        api.getBatches().catch(() => []),
        api.getMemo().catch(() => null),
        api.getAuditLog().catch(() => []),
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
        `Seeded sample dataset: ${res.findings_created} planted anomalies detected (₹${res.total_at_risk?.toLocaleString("en-IN")} at risk).`,
        "success",
        "Demo Dataset Loaded"
      );
      const freshFindings = await api.getFindings().catch(() => []);
      await loadData();
      if (freshFindings.length > 0) {
        await handleSelectFinding(freshFindings[0].finding_id);
      }
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

  const handleUploadFile = async (kind, file) => {
    const up = await api.uploadDocument(kind, file);
    await api.runExtract(up.batch_id);
    await api.runDetect(up.batch_id);
    showToast(`Uploaded, extracted & audited ${file.name} (${up.batch_id}).`, "success", "Pipeline Complete");
    await loadData();
    return up;
  };

  const handleMakeDecision = async (findingId, action, reviewer, note) => {
    setIsSubmittingDecision(true);
    try {
      const res = await api.postDecision(findingId, action, reviewer, note);
      showToast(
        `Finding ${findingId} marked "${res.status}". Immutable audit row recorded.`,
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

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        isOnline={isOnline}
        onSeedDemo={handleSeedDemo}
        onOpenUploadModal={() => setUploadModalOpen(true)}
        loadingAction={loadingAction}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === "dashboard" && (
          <DashboardView
            stats={stats}
            findings={findings}
            onSelectFinding={handleSelectFinding}
            onNavigateTab={setActiveTab}
            onSeedDemo={handleSeedDemo}
            loadingAction={loadingAction}
          />
        )}

        {activeTab === "findings" && (
          <FindingsView
            findings={findings}
            selectedFindingId={selectedFindingId}
            selectedFindingDetail={selectedFindingDetail}
            onSelectFinding={handleSelectFinding}
            onMakeDecision={handleMakeDecision}
            isSubmittingDecision={isSubmittingDecision}
            onSeedDemo={handleSeedDemo}
            loadingAction={loadingAction}
          />
        )}

        {activeTab === "upload" && (
          <UploadView
            batches={batches}
            onUploadFile={handleUploadFile}
            onSeedDemo={handleSeedDemo}
            onRunDetect={handleRunDetect}
            loadingAction={loadingAction}
          />
        )}

        {activeTab === "memo" && (
          <MemoView
            memoData={memoData}
            onRefreshMemo={loadData}
            onCopy={() => showToast("Audit memo copied to clipboard.", "success")}
          />
        )}

        {activeTab === "rules" && <RulesView />}

        {activeTab === "audit" && (
          <AuditLogView
            logs={auditLogs}
            onSelectFinding={(id) => {
              handleSelectFinding(id);
              setActiveTab("findings");
            }}
          />
        )}
      </main>

      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onPipelineComplete={async () => {
          await loadData();
          setActiveTab("findings");
        }}
      />

      <Toast toast={toast} onClose={() => setToast(null)} />

      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>LedgerLens — Explainable AI Money-Leak Auditor</span>
          <span>Startup Buildathon India 2026 · Gemini 4 Carbon · Deterministic Rules R1–R5</span>
        </div>
      </footer>
    </div>
  );
}
