import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  FileCheck2,
  Loader2,
  Send,
  Terminal,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../api";
import { useAccountMemory } from "../context/AccountMemoryContext";

const SUGGESTED_QUESTIONS = [
  "What is our total at-risk exposure?",
  "Summarize the highest-severity anomalies",
  "Which vendors have duplicate or overbilled invoices?",
];

export function CopilotDrawer({
  isOpen,
  onClose,
  activeWorkspaceId = "default",
  currentPage = "",
  selectedFinding = null,
}) {
  const wsId = activeWorkspaceId || "default";
  const {
    getCopilotHistoryForWorkspace,
    appendCopilotMessage,
    clearCopilotHistory,
    recordPageActivity,
  } = useAccountMemory();

  const history = getCopilotHistoryForWorkspace(wsId);

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastResult, setLastResult] = useState(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !loading) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose, loading]);

  if (!isOpen) return null;

  const submitQuestion = async (rawQuestion) => {
    const trimmed = rawQuestion.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError("");
    try {
      const hasContext =
        Boolean(currentPage) || Boolean(selectedFinding) || history.length > 0;

      const data = hasContext
        ? await api.askCopilot(trimmed, wsId, {
            currentPage: currentPage || undefined,
            selectedFindingId: selectedFinding?.finding_id || undefined,
            selectedFinding: selectedFinding
              ? {
                  finding_id: selectedFinding.finding_id,
                  rule_id: selectedFinding.rule_id,
                  title: selectedFinding.title,
                  amount_at_risk: selectedFinding.amount_at_risk,
                  currency: selectedFinding.currency,
                  status: selectedFinding.status,
                }
              : undefined,
            conversationHistory: history.slice(-6).map((item) => ({
              question: item.question,
              answer: item.answer,
            })),
          })
        : await api.askCopilot(trimmed, wsId);

      const entry = {
        id: `cp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        question: trimmed,
        answer: data?.answer || "",
        mode: data?.mode || "deterministic",
        citations: data?.citations ?? data?.findings ?? [],
        timestamp: new Date().toISOString(),
      };

      setLastResult(entry);
      appendCopilotMessage(wsId, entry);
      recordPageActivity("copilot", "Asked Copilot", trimmed.slice(0, 60));
      setQuestion("");
    } catch (err) {
      setError(err?.message || "Failed to query CFO Copilot.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submitQuestion(question);
  };

  // Show persisted history, or fall back to lastResult if rendered without Provider
  const displayEntries =
    history.length > 0 ? history : lastResult ? [lastResult] : [];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="CFO Copilot Drawer"
    >
      <div
        className="fixed inset-0 bg-slate-900/40 transition-opacity"
        onClick={() => !loading && onClose()}
      />

      <div className="relative z-10 w-full max-w-xl bg-white border-l border-[#E2E8F0] shadow-lg flex flex-col h-full">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
          <div className="space-y-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 text-slate-900 border border-[#E2E8F0]">
                <Terminal className="w-3 h-3 text-slate-700" aria-hidden="true" />
                CFO Copilot
              </span>
              <span className="font-mono text-[11px] text-slate-500 truncate">
                workspace: {wsId}
              </span>
              {currentPage && (
                <span className="font-mono text-[11px] text-slate-500">
                  · page: {currentPage}
                </span>
              )}
              {selectedFinding?.finding_id && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white border border-[#E2E8F0] text-slate-700">
                  {selectedFinding.finding_id}
                </span>
              )}
            </div>
            <h2 className="text-[15px] font-semibold text-slate-900 tracking-[-0.01em]">
              Grounded Audit Assistant
            </h2>
            <p className="text-xs text-slate-500">
              Ask questions grounded in your verified flagged bills and contract records.
            </p>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {displayEntries.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  clearCopilotHistory(wsId);
                  setLastResult(null);
                }}
                disabled={loading}
                aria-label="Clear Copilot history"
                title="Clear conversation history"
                className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-200/70 transition-colors disabled:opacity-50"
              >
                <Trash2 className="w-4 h-4" aria-hidden="true" />
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              aria-label="Close Copilot"
              className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-200/70 transition-colors disabled:opacity-50"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-4 space-y-4 bg-white">
          {/* Quick Prompts */}
          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
              Suggested Prompts
            </p>
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTED_QUESTIONS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={loading}
                  onClick={() => {
                    setQuestion(prompt);
                    submitQuestion(prompt);
                  }}
                  className="px-2.5 py-1.5 rounded-md text-xs text-slate-700 bg-[#F8FAFC] hover:bg-slate-100 border border-[#E2E8F0] transition-colors text-left disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Conversation History */}
          {displayEntries.map((entry) => {
            const citedFindings = entry.citations || [];
            return (
              <div key={entry.id} className="space-y-3 pt-2 border-t border-[#E2E8F0] first:border-t-0 first:pt-0">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-md bg-slate-900 text-white px-3 py-2 text-xs leading-relaxed">
                    {entry.question}
                  </div>
                </div>

                <div className="rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3.5 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                      Grounded Answer
                    </span>
                    {entry.mode && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] leading-none font-mono bg-white text-slate-700 border border-[#E2E8F0]">
                        {entry.mode}
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] text-slate-900 leading-relaxed whitespace-pre-wrap">
                    {typeof entry.answer === "string"
                      ? entry.answer
                      : JSON.stringify(entry.answer ?? "")}
                  </p>
                </div>

                {citedFindings.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                      <FileCheck2 className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>Cited Findings ({citedFindings.length})</span>
                    </div>
                    <div className="space-y-2">
                      {citedFindings.map((item, idx) => (
                        <div
                          key={item.finding_id || `citation-${idx}`}
                          className="rounded-md border border-[#E2E8F0] bg-white p-3 space-y-1.5"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              {item.finding_id && (
                                <span className="font-mono text-xs font-semibold text-slate-900">
                                  {item.finding_id}
                                </span>
                              )}
                              {item.rule_id && (
                                <span className="px-1.5 py-0.5 rounded text-[11px] leading-none font-mono bg-slate-100 text-slate-700 border border-[#E2E8F0]">
                                  {item.rule_id}
                                </span>
                              )}
                            </div>
                            {item.amount_at_risk !== undefined &&
                              item.amount_at_risk !== null && (
                                <span className="font-mono text-xs font-medium text-slate-900 tabular-nums text-right">
                                  {item.currency ? `${item.currency} ` : ""}
                                  {Number(item.amount_at_risk).toLocaleString("en-IN")}
                                </span>
                              )}
                          </div>
                          {item.proof_trail && (
                            <p className="text-xs text-slate-600 break-words">
                              {typeof item.proof_trail === "string"
                                ? item.proof_trail
                                : [
                                    item.proof_trail.recommended_action
                                      ? `Recommended: ${String(item.proof_trail.recommended_action).replace(/_/g, " ")}`
                                      : null,
                                    item.proof_trail.math &&
                                    typeof item.proof_trail.math === "object"
                                      ? Object.entries(item.proof_trail.math)
                                          .slice(0, 4)
                                          .map(([k, v]) => `${k}: ${v}`)
                                          .join(" · ")
                                      : null,
                                  ]
                                    .filter(Boolean)
                                    .join(" — ") || "Verified against contract & PO records."}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Loading State */}
          {loading && (
            <div className="flex items-center gap-2.5 p-3.5 rounded-md border border-[#E2E8F0] bg-[#F8FAFC] text-xs text-slate-700">
              <Loader2 className="w-4 h-4 animate-spin text-slate-900 shrink-0" aria-hidden="true" />
              <span>Analyzing grounded findings and proof trails…</span>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2.5 p-3.5 rounded-md border border-[#FECACA] bg-[#FEF2F2] text-xs text-[#991B1B]"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-[#DC2626]" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer Input Form */}
        <form
          onSubmit={handleSubmit}
          className="px-5 py-3.5 border-t border-[#E2E8F0] bg-[#F8FAFC] flex items-center gap-2"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about findings, vendors, or proof-trail math…"
            aria-label="Ask CFO Copilot"
            disabled={loading}
            className="flex-1 h-9 px-3 text-[13px] rounded-md border border-[#CBD5E1] bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center gap-1.5 h-9 px-3.5 text-xs font-medium rounded-md bg-slate-900 hover:bg-slate-800 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Ask</span>
          </button>
        </form>
      </div>
    </div>
  );
}
