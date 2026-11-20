import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "./components/Navbar";
import { Toast } from "./components/Toast";
import { DashboardView } from "./views/DashboardView";
import { FindingsView } from "./views/FindingsView";
import { FindingDetailModal } from "./views/FindingDetailModal";
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
  const [memoText, setMemoText] = useState("");
  const [isOnline, setIsOnline] = useState(true);
  const [loadingAction, setLoadingAction] = useState(false);
  const [toast, setToast] = useState(null);

  // Finding Detail Modal
  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [selectedFindingDetail, setSelectedFindingDetail] = useState(null);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  const showToast = (message, type = "info", title = "") => {
    setToast({ message, type, title });
    setTimeout(() => {
      setToast((curr) => (curr?.message === message ? null : curr));
    }, 4000);
  };

  const loadData = useCallback(async () => {
    try {
      const [h, s, f, b, m, l] = await Promise.all([
        api.getHealth().catch(() => ({ status: "offline" })),
        api.getStats().catch(() => null),
        api.getFindings().catch(() => []),
        api.getBatches().catch(() => []),
        api.getMemo().catch(() => ({ memo_markdown: "" })),
        api.getAuditLog().catch(() => []),
      ]);

      setIsOnline(h.status === "ok");
      if (s) setStats(s);
      if (f) setFindings(f);
      if (b) setBatches(b);
      if (m?.memo_markdown) setMemoText(m.memo_markdown);
      if (l) setAuditLogs(l);
    } catch {
      setIsOnline(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000); // 15s poll
    return () => clearInterval(interval);
  }, [loadData]);

  // Handle Demo Seed
  const handleSeedDemo = async () => {
    setLoadingAction(true);
    try {
      const res = await api.seedSampleData();
      showToast(
        `Loaded 5 sample datasets with ${res.findings_created} planted anomalies (₹${res.total_at_risk?.toLocaleString()} at risk).`,
        "success",
        "Demo Dataset Loaded"
      );
      await loadData();
    } catch (err) {
      showToast(err.message, "error", "Seed Failed");
    } finally {
      setLoadingAction(false);
    }
  };

  // Handle Run Detection
  const handleRunDetect = async () => {
    setLoadingAction(true);
    try {
      const res = await api.runGlobalDetect();
      showToast(
        `Audit engine verified tables: ${res.findings_created} active spend exception(s) detected.`,
        "success",
        "Detection Engine Complete"
      );
      await loadData();
    } catch (err) {
      showToast(err.message, "error", "Detection Failed");
    } finally {
      setLoadingAction(false);
    }
  };

  // Handle File Upload
  const handleUploadFile = async (kind, file) => {
    const res = await api.uploadDocument(kind, file);
    showToast(`Uploaded ${file.name} (${res.rows_detected} rows detected).`, "success", "Upload Registered");
    await loadData();
    return res;
  };

  // Handle Select Finding for Detail Modal
  const handleSelectFinding = async (findingId) => {
    setSelectedFindingId(findingId);
    try {
      const detail = await api.getFinding(findingId);
      setSelectedFindingDetail(detail);
    } catch (err) {
      showToast(err.message, "error", "Failed to Load Finding");
    }
  };

  // Handle Reviewer Decision
  const handleMakeDecision = async (findingId, action, reviewer, note) => {
    setIsSubmittingDecision(true);
    try {
      const res = await api.postDecision(findingId, action, reviewer, note);
      showToast(
        `Finding ${findingId} updated to status "${res.status}". Audit row logged.`,
        "success",
        "Decision Recorded"
      );
      // Reload updated detail
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
    <div className="min-h-screen bg-[#090D16] text-slate-100 flex flex-col font-sans selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        isOnline={isOnline}
        onSeedDemo={handleSeedDemo}
        onRunDetect={handleRunDetect}
        loadingAction={loadingAction}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
            onSelectFinding={handleSelectFinding}
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
            memoText={memoText}
            stats={stats}
            onCopy={() => showToast("Audit memo copied to clipboard!", "success")}
          />
        )}

        {activeTab === "rules" && <RulesView />}

        {activeTab === "audit" && (
          <AuditLogView
            logs={auditLogs}
            onSelectFinding={handleSelectFinding}
          />
        )}
      </main>

      {/* Finding Detail Modal */}
      <FindingDetailModal
        isOpen={!!selectedFindingId}
        onClose={() => {
          setSelectedFindingId(null);
          setSelectedFindingDetail(null);
        }}
        finding={selectedFindingDetail}
        onMakeDecision={handleMakeDecision}
        isSubmitting={isSubmittingDecision}
      />

      {/* Floating Toast Notification */}
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>LedgerLens — Explainable AI Spend Auditor</span>
          <span>Google AI Buildathon · Gemini 2.5 Flash · Pure Deterministic Proofs</span>
        </div>
      </footer>
    </div>
  );
}
