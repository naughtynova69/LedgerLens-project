import React from "react";
import {
  PlayCircle,
  Database,
  FileSearch,
  CheckCircle2,
  ShieldCheck,
  MessageSquare,
  Upload,
  ArrowRight,
  Network,
} from "lucide-react";
import { Modal } from "./Modal";

export function DemoGuideModal({
  isOpen,
  onClose,
  onSeedDemo,
  onNavigateTab,
  onOpenCopilot,
  onOpenMemo,
  onOpenUpload,
  loadingAction,
}) {
  const steps = [
    {
      num: "01",
      title: "Load the Demo Dataset (6 Planted Anomalies + 4 Clean Controls)",
      where: "Top-right navbar → Load Demo",
      how: "Click Load Demo. This seeds 10 realistic AP invoices across 9 vendors, runs deterministic rules R1–R10, and syncs the LadybugDB Knowledge Graph.",
      highlight:
        "Point out that 4 clean control invoices (INV-9001, INV-9010, INV-9400, INV-9500) produce 0 false positives.",
      icon: Database,
      actionLabel: loadingAction ? "Loading..." : "Load Demo Now",
      onAction: async () => {
        await onSeedDemo();
        onClose();
      },
      disabled: loadingAction,
    },
    {
      num: "02",
      title: "Inspect the 3-Way Match & Proof Trail",
      where: "Exceptions tab → Left table → Click any row",
      how: "Click R1 Duplicate (INV-8821 vs INV-8821-R2) or R2 Price Leakage (INV-9102). Inspect the right-hand Proof Trail pane, 3-Way Evidence Diff, and Proof Math.",
      highlight:
        "Show that deterministic Python rules make the decision, while Gemini narrates strictly from the proof_trail.",
      icon: FileSearch,
      actionLabel: "Go to Exceptions",
      onAction: () => {
        onNavigateTab("exceptions");
        onClose();
      },
    },
    {
      num: "03",
      title: "Record a Human Decision & Watch KPIs Update Live",
      where: "Exceptions tab → Right pane → Action buttons",
      how: "Enter an audit note (optional) and click Hold / Recover, Dispute, or Approve. You can also select multiple rows via checkboxes for Bulk Triage.",
      highlight:
        "Recovered (INR) KPI jumps immediately and the decision is appended to the cryptographic audit trail.",
      icon: CheckCircle2,
      actionLabel: "Review Exceptions",
      onAction: () => {
        onNavigateTab("exceptions");
        onClose();
      },
    },
    {
      num: "04",
      title: "Verify Cryptographic Audit Log & Knowledge Graph",
      where: "Activity tab → Verify Ledger Integrity | Rules & Graph tab",
      how: "Open Activity and click Verify Ledger Integrity to validate the SHA-256 hash chain. Open Rules & Graph to inspect R1–R10 logic and multi-hop vendor/bank/approver links.",
      highlight:
        "Demonstrates full auditability for CFOs & statutory auditors plus cross-entity collusion detection (R8–R10).",
      icon: ShieldCheck,
      actionLabel: "Open Activity",
      onAction: () => {
        onNavigateTab("activity");
        onClose();
      },
      secondaryLabel: "Open Rules & Graph",
      onSecondaryAction: () => {
        onNavigateTab("rules");
        onClose();
      },
    },
    {
      num: "05",
      title: "Ask CFO Copilot & Export Board-Ready CFO Memo",
      where: "Top-right navbar → CFO Copilot & CFO Memo",
      how: "Open CFO Copilot and ask 'Which vendor has the highest risk?' or 'Summarize open duplicates'. Then open CFO Memo to copy or download the Markdown executive report.",
      highlight:
        "Answers are grounded in live findings and proof trails—zero hallucinated numbers.",
      icon: MessageSquare,
      actionLabel: "Open CFO Copilot",
      onAction: () => {
        onClose();
        onOpenCopilot();
      },
      secondaryLabel: "Open CFO Memo",
      onSecondaryAction: () => {
        onClose();
        onOpenMemo();
      },
    },
    {
      num: "06",
      title: "Live Document Upload (PDF / Image / CSV)",
      where: "Top-right navbar → Upload",
      how: "Click Upload to drop a vendor invoice PDF, image, or CSV batch. Gemini Vision extracts line items with Pydantic schema validation and runs R1–R10 immediately.",
      highlight:
        "Low-confidence lines are automatically quarantined to the Needs Review drawer for human sign-off.",
      icon: Upload,
      actionLabel: "Open Upload",
      onAction: () => {
        onClose();
        onOpenUpload();
      },
    },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="LedgerLens Live Demo Guide & Walkthrough"
      maxWidth="max-w-3xl"
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 border border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <PlayCircle className="w-4 h-4 text-slate-700 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-slate-900">
                3-Minute Interactive Demo Script
              </p>
              <p className="text-[11px] text-slate-500">
                Follow steps 01–06 in order, or click any quick-jump button to open that surface directly.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-600">
            <Network className="w-3.5 h-3.5 text-slate-600" />
            <span>Shortcuts: j/k navigate · / search</span>
          </div>
        </div>

        <div className="space-y-3">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.num}
                className="rounded-lg border border-slate-200 bg-white p-4 hover:border-slate-300 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-6 h-6 rounded bg-slate-900 text-white font-mono text-[11px] font-semibold tabular-nums flex items-center justify-center shrink-0 mt-0.5">
                      {step.num}
                    </div>
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2">
                        <Icon className="w-3.5 h-3.5 text-slate-700 shrink-0" />
                        <h3 className="text-[13px] font-semibold text-slate-900">
                          {step.title}
                        </h3>
                      </div>
                      <p className="text-xs text-slate-600">
                        <span className="font-semibold text-slate-900">Where: </span>
                        <span className="font-mono text-[11px] bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded border border-slate-200">
                          {step.where}
                        </span>
                      </p>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        <span className="font-semibold text-slate-800">How: </span>
                        {step.how}
                      </p>
                      <p className="text-[11px] text-[#065F46] bg-[#ECFDF5] border border-[#A7F3D0] rounded px-2.5 py-1.5">
                        <span className="font-semibold">Demo talking point: </span>
                        {step.highlight}
                      </p>
                    </div>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={step.onAction}
                      disabled={step.disabled}
                      className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition-colors disabled:opacity-50 whitespace-nowrap focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
                    >
                      <span>{step.actionLabel}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                    {step.secondaryLabel && (
                      <button
                        type="button"
                        onClick={step.onSecondaryAction}
                        className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
                      >
                        <span>{step.secondaryLabel}</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Modal>
  );
}
