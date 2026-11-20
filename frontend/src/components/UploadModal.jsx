import React, { useState } from "react";
import { UploadCloud, CheckCircle2, AlertCircle, Loader2, FileText } from "lucide-react";
import { Modal } from "./Modal";
import { api } from "../api";

export function UploadModal({ isOpen, onClose, onPipelineComplete }) {
  const [kind, setKind] = useState("invoices");
  const [file, setFile] = useState(null);
  const [step, setStep] = useState("idle"); // idle | uploading | extracting | detecting | done | error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setErrorMsg("");
    setResult(null);

    try {
      setStep("uploading");
      const up = await api.uploadDocument(kind, file);

      setStep("extracting");
      const ext = await api.runExtract(up.batch_id);

      setStep("detecting");
      const det = await api.runDetect(up.batch_id);

      setStep("done");
      setResult({ upload: up, extract: ext, detect: det });
      if (onPipelineComplete) {
        await onPipelineComplete(up, ext, det);
      }
    } catch (err) {
      setStep("error");
      setErrorMsg(err.message || "Pipeline execution failed");
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Upload CSV / PDF & Run Audit Pipeline" maxWidth="max-w-xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            Document Feed Kind
          </label>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-600"
          >
            <option value="invoices">Invoices (CSV or PDF scan)</option>
            <option value="purchase_orders">Purchase Orders (CSV or PDF)</option>
            <option value="contracts">Vendor Contracts (CSV or PDF)</option>
            <option value="payments">Payment Ledger (CSV)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            Select File (`.csv` or `.pdf`)
          </label>
          <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-slate-300 rounded-xl bg-slate-50 hover:bg-slate-100/70 cursor-pointer transition-colors">
            <UploadCloud className="w-8 h-8 text-slate-400 mb-2" />
            <span className="text-sm font-medium text-slate-700">
              {file ? file.name : "Choose CSV or PDF invoice/contract document"}
            </span>
            <span className="text-xs text-slate-500 mt-1">
              Pipeline runs Upload → Gemini Extract → Deterministic Rules R1–R5
            </span>
            <input
              type="file"
              accept=".csv,.pdf,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
            />
          </label>
        </div>

        {step !== "idle" && (
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs">
            <div className="flex items-center justify-between font-semibold text-slate-700">
              <span>Pipeline Status</span>
              <span className="font-mono uppercase">{step}</span>
            </div>
            {["uploading", "extracting", "detecting"].includes(step) && (
              <div className="flex items-center gap-2 text-[#4F46E5]">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running {step}...</span>
              </div>
            )}
            {step === "error" && (
              <div className="flex items-center gap-2 text-[#DC2626]">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
            {step === "done" && result && (
              <div className="space-y-1 text-[#059669]">
                <div className="flex items-center gap-1.5 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>
                    Batch {result.upload.batch_id} complete ({result.extract.rows_extracted} rows extracted via{" "}
                    {result.extract.model}, {result.detect.findings_created} findings).
                  </span>
                </div>
                {result.extract.verification_warnings?.length > 0 && (
                  <p className="text-[#D97706] flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" />
                    {result.extract.verification_warnings[0].message}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
          <button
            type="submit"
            disabled={!file || ["uploading", "extracting", "detecting"].includes(step)}
            className="px-4 py-2 rounded-lg bg-[#059669] hover:bg-[#047857] text-white text-xs font-semibold disabled:opacity-50"
          >
            Upload, Extract & Audit
          </button>
        </div>
      </form>
    </Modal>
  );
}
