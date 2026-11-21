import React, { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
  UploadCloud,
} from "lucide-react";
import { Modal } from "./Modal";
import { api } from "../api";

const PIPELINE_STEPS = [
  { id: "uploading", label: "Upload" },
  { id: "extracting", label: "Extract" },
  { id: "detecting", label: "Detect" },
  { id: "explaining", label: "Explain" },
];

export function UploadModal({ isOpen, onClose, onPipelineComplete }) {
  const [kind, setKind] = useState("invoices");
  const [file, setFile] = useState(null);
  const [step, setStep] = useState("idle"); // idle | uploading | extracting | detecting | explaining | done | error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const isRunning = ["uploading", "extracting", "detecting", "explaining"].includes(step);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || isRunning) return;
    setErrorMsg("");
    setResult(null);

    try {
      setStep("uploading");
      const up = await api.uploadDocument(kind, file, true);

      const pipeline = up?.pipeline || {};
      const hasFullPipeline =
        Boolean(up?.auto_run) ||
        Boolean(up?.pipeline) ||
        Boolean(up?.extract) ||
        Boolean(up?.detect) ||
        up?.findings_created !== undefined;

      if (hasFullPipeline) {
        setStep("explaining");
        const extractInfo = up.extract || pipeline.extract || {
          rows_extracted:
            pipeline.rows_extracted ?? up.rows_extracted ?? up.rows_detected ?? 0,
          model: pipeline.model || up.model || "deterministic",
          verification_warnings:
            pipeline.verification_warnings || up.verification_warnings || [],
        };
        const detectInfo = up.detect || pipeline.detect || {
          findings_created: pipeline.findings_created ?? up.findings_created ?? 0,
        };
        setStep("done");
        setResult({ upload: up, extract: extractInfo, detect: detectInfo });
        if (onPipelineComplete) {
          await onPipelineComplete(up, extractInfo, detectInfo);
        }
        return;
      }

      setStep("extracting");
      const ext = await api.runExtract(up.batch_id);

      setStep("detecting");
      const det = await api.runDetect(up.batch_id);

      setStep("explaining");
      setStep("done");
      setResult({ upload: up, extract: ext, detect: det });
      if (onPipelineComplete) {
        await onPipelineComplete(up, ext, det);
      }
    } catch (err) {
      setStep("error");
      setErrorMsg(err.message || "Automated pipeline failed. Check file format and retry.");
    }
  };

  const activeIdx = PIPELINE_STEPS.findIndex((s) => s.id === step);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Automated Document Audit Pipeline"
      maxWidth="max-w-lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="upload-feed-kind"
            className="block text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 mb-1.5"
          >
            Document Feed Kind
          </label>
          <select
            id="upload-feed-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            disabled={isRunning}
            className="w-full h-9 px-3 bg-white border border-[#CBD5E1] rounded-md text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            <option value="invoices">Invoices (CSV or PDF scan)</option>
            <option value="purchase_orders">Purchase Orders (CSV or PDF)</option>
            <option value="contracts">Vendor Contracts (CSV or PDF)</option>
            <option value="payments">Payment Ledger (CSV)</option>
          </select>
        </div>

        <div>
          <span className="block text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 mb-1.5">
            Select File (.csv or .pdf)
          </span>
          <label className="flex flex-col items-center justify-center p-6 border border-dashed border-[#CBD5E1] rounded-md bg-[#F8FAFC] hover:bg-slate-100/70 cursor-pointer transition-colors">
            <UploadCloud className="w-5 h-5 text-slate-500 mb-2" aria-hidden="true" />
            <span className="text-xs font-medium text-slate-900 text-center break-all">
              {file ? file.name : "Choose CSV or PDF invoice/contract document"}
            </span>
            <span className="text-[11px] text-slate-500 mt-1">
              Single-click flow: Upload → Extract → Detect (R1–R10) → Explain
            </span>
            <input
              type="file"
              accept=".csv,.pdf,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={isRunning}
              className="sr-only"
            />
          </label>
        </div>

        {step !== "idle" && (
          <div className="p-3.5 rounded-md border border-[#E2E8F0] bg-[#F8FAFC] space-y-2.5 text-xs">
            <div className="flex items-center justify-between font-medium text-slate-900">
              <span>Automated Pipeline</span>
              <span className="font-mono uppercase text-[11px] text-slate-500">{step}</span>
            </div>

            {/* 4-Step Progress Strip */}
            <div className="grid grid-cols-4 gap-1.5">
              {PIPELINE_STEPS.map((s, idx) => {
                const isDone = step === "done" || (activeIdx > idx && step !== "error");
                const isCurrent = step === s.id;
                return (
                  <div
                    key={s.id}
                    className={`px-2 py-1 rounded border text-center text-[11px] font-medium transition-colors ${
                      isDone
                        ? "bg-[#ECFDF5] border-[#A7F3D0] text-[#065F46]"
                        : isCurrent
                        ? "bg-white border-slate-900 text-slate-900"
                        : "bg-white border-[#E2E8F0] text-slate-400"
                    }`}
                  >
                    {s.label}
                  </div>
                );
              })}
            </div>

            {isRunning && (
              <div className="flex items-center gap-2 text-slate-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-900" aria-hidden="true" />
                <span>Running {step}…</span>
              </div>
            )}

            {step === "error" && (
              <div role="alert" className="flex items-center gap-2 text-[#991B1B]">
                <AlertCircle className="w-4 h-4 shrink-0 text-[#DC2626]" aria-hidden="true" />
                <span>{errorMsg}</span>
              </div>
            )}

            {step === "done" && result && (
              <div className="space-y-1 text-[#065F46]">
                <div className="flex items-center gap-1.5 font-medium">
                  <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
                  <span className="tabular-nums">
                    Batch {result.upload.batch_id} complete ({result.extract.rows_extracted} rows via{" "}
                    {result.extract.model}, {result.detect.findings_created} findings).
                  </span>
                </div>
                {result.extract.verification_warnings?.length > 0 && (
                  <p className="text-slate-600 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" aria-hidden="true" />
                    {result.extract.verification_warnings[0].message}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="h-8 px-3.5 rounded-md border border-[#E2E8F0] bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 transition-colors"
          >
            Close
          </button>
          <button
            type="submit"
            disabled={!file || isRunning}
            className="h-8 px-3.5 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition-colors disabled:opacity-50"
          >
            {isRunning ? "Running Pipeline…" : "Upload & Run Full Audit"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
