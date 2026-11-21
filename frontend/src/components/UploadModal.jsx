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
    <Modal isOpen={isOpen} onClose={onClose} title="Upload CSV / PDF & Run Audit" maxWidth="max-w-lg">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 mb-1.5">
            Document Feed Kind
          </label>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="w-full h-9 px-3 bg-white border border-slate-300 rounded-md text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            <option value="invoices">Invoices (CSV or PDF scan)</option>
            <option value="purchase_orders">Purchase Orders (CSV or PDF)</option>
            <option value="contracts">Vendor Contracts (CSV or PDF)</option>
            <option value="payments">Payment Ledger (CSV)</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 mb-1.5">
            Select File (.csv or .pdf)
          </label>
          <label className="flex flex-col items-center justify-center p-6 border border-dashed border-slate-300 rounded-lg bg-slate-50 hover:bg-slate-100/70 cursor-pointer transition-colors">
            <UploadCloud className="w-5 h-5 text-slate-500 mb-2" />
            <span className="text-xs font-medium text-slate-900">
              {file ? file.name : "Choose CSV or PDF invoice/contract document"}
            </span>
            <span className="text-[11px] text-slate-500 mt-1">
              Upload → Gemini Extract → Deterministic Rules R1–R10
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
          <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50 space-y-2 text-xs">
            <div className="flex items-center justify-between font-medium text-slate-900">
              <span>Pipeline Status</span>
              <span className="font-mono uppercase text-[11px] text-slate-500">{step}</span>
            </div>
            {["uploading", "extracting", "detecting"].includes(step) && (
              <div className="flex items-center gap-2 text-slate-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-900" />
                <span>Running {step}...</span>
              </div>
            )}
            {step === "error" && (
              <div className="flex items-center gap-2 text-[#B91C1C]">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
            {step === "done" && result && (
              <div className="space-y-1 text-[#047857]">
                <div className="flex items-center gap-1.5 font-medium">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span className="tabular-nums">
                    Batch {result.upload.batch_id} complete ({result.extract.rows_extracted} rows via{" "}
                    {result.extract.model}, {result.detect.findings_created} findings).
                  </span>
                </div>
                {result.extract.verification_warnings?.length > 0 && (
                  <p className="text-slate-600 flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" />
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
            className="h-8 px-3.5 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 transition-colors focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
          >
            Close
          </button>
          <button
            type="submit"
            disabled={!file || ["uploading", "extracting", "detecting"].includes(step)}
            className="h-8 px-3.5 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
          >
            Upload &amp; Run Audit
          </button>
        </div>
      </form>
    </Modal>
  );
}
