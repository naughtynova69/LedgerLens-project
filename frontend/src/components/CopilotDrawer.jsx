import React, { useEffect, useState } from "react";
import { AlertCircle, FileCheck2, Loader2, Send, Sparkles, X } from "lucide-react";
import { api } from "../api";

const SUGGESTED_QUESTIONS = [
  "What is our total at-risk exposure?",
  "Summarize the highest-severity anomalies",
  "Which vendors have duplicate or overbilled invoices?",
];

export function CopilotDrawer({
  isOpen,
  onClose,
  activeWorkspaceId = "default",
}) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

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
      const data = await api.askCopilot(trimmed, activeWorkspaceId || "default");
      setResult(data);
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

  const citedFindings = result?.citations ?? result?.findings ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="CFO Copilot Drawer"
    >
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
        onClick={() => !loading && onClose()}
      />

      <div className="relative z-10 w-full max-w-xl bg-white border-l border-[#E5E7EB] shadow-2xl flex flex-col h-full">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-[#E5E7EB] bg-[#F8FAFC]">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-white text-[#111827] border border-[#E5E7EB]">
                <Sparkles className="w-3 h-3 text-gray-600" />
                CFO Copilot
              </span>
              <span className="font-mono text-[11px] text-gray-500 truncate">
                workspace: {activeWorkspaceId || "default"}
              </span>
            </div>
            <h2 className="text-base font-semibold text-[#111827] tracking-tight">
              Grounded Audit Assistant
            </h2>
            <p className="text-xs text-gray-500">
              Ask questions grounded in deterministic R1–R5 findings and proof-trail math.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            aria-label="Close Copilot"
            className="p-1.5 rounded-lg text-gray-500 hover:text-[#111827] hover:bg-gray-200/70 transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 bg-white">
          {/* Quick Prompts */}
          <div className="space-y-2">
            <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
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
                  className="px-2.5 py-1 rounded-lg text-xs text-gray-700 bg-[#F8FAFC] hover:bg-gray-100 border border-[#E5E7EB] transition-colors text-left disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Loading State */}
          {loading && (
            <div className="flex items-center gap-2.5 p-4 rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] text-xs text-gray-700">
              <Loader2 className="w-4 h-4 animate-spin text-[#111827] shrink-0" />
              <span>Analyzing grounded findings and proof trails...</span>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2.5 p-3.5 rounded-xl border border-red-200 bg-red-50 text-xs text-red-800"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-700" />
              <span>{error}</span>
            </div>
          )}

          {/* Answer & Citations */}
          {result && !loading && (
            <div className="space-y-4">
              <div className="rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    Grounded Answer
                  </span>
                  {result.mode && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-mono bg-white text-gray-700 border border-[#E5E7EB]">
                      {result.mode}
                    </span>
                  )}
                </div>
                <p className="text-sm text-[#111827] leading-relaxed whitespace-pre-wrap">
                  {result.answer}
                </p>
              </div>

              {citedFindings.length > 0 && (
                <div className="space-y-2.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    <FileCheck2 className="w-3.5 h-3.5" />
                    <span>Cited Findings ({citedFindings.length})</span>
                  </div>
                  <div className="space-y-2">
                    {citedFindings.map((item, idx) => (
                      <div
                        key={item.finding_id || `citation-${idx}`}
                        className="rounded-lg border border-[#E5E7EB] bg-white p-3 space-y-1.5"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            {item.finding_id && (
                              <span className="font-mono text-xs font-semibold text-[#111827]">
                                {item.finding_id}
                              </span>
                            )}
                            {item.rule_id && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#F8FAFC] text-gray-700 border border-[#E5E7EB]">
                                {item.rule_id}
                              </span>
                            )}
                          </div>
                          {item.amount_at_risk !== undefined && item.amount_at_risk !== null && (
                            <span className="font-mono text-xs font-medium text-[#111827] tabular-nums">
                              {item.currency ? `${item.currency} ` : ""}
                              {Number(item.amount_at_risk).toLocaleString("en-IN")}
                            </span>
                          )}
                        </div>
                        {item.proof_trail && (
                          <p className="text-xs text-gray-600 font-mono break-words">
                            {item.proof_trail}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Input Form */}
        <form
          onSubmit={handleSubmit}
          className="px-6 py-4 border-t border-[#E5E7EB] bg-[#F8FAFC] flex items-center gap-2"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about findings, vendors, or proof-trail math..."
            aria-label="Ask CFO Copilot"
            disabled={loading}
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-[#E5E7EB] bg-white text-[#111827] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#111827]/15 focus:border-[#111827] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-[#111827] hover:bg-gray-800 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Ask</span>
          </button>
        </form>
      </div>
    </div>
  );
}
