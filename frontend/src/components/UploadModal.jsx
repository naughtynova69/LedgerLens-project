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
          <label className="block text-xs font-medium text-[#111827] mb-1.5">
            Document Feed Kind
          </label>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs text-[#111827] focus:outline-none focus:border-gray-400"
          >
            <option value="invoices">Invoices (CSV or PDF scan)</option>
            <option value="purchase_orders">Purchase Orders (CSV or PDF)</option>
            <option value="contracts">Vendor Contracts (CSV or PDF)</option>
            <option value="payments">Payment Ledger (CSV)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-[#111827] mb-1.5">
            Select File (.csv or .pdf)
          </label>
          <label className="flex flex-col items-center justify-center p-6 border border-dashed border-gray-300 rounded-lg bg-[#FAFAFA] hover:bg-gray-50 cursor-pointer transition-colors">
            <UploadCloud className="w-6 h-6 text-[#6B7280] mb-2" />
            <span className="text-xs font-medium text-[#111827]">
              {file ? file.name : "Choose CSV or PDF invoice/contract document"}
            </span>
            <span className="text-[11px] text-[#6B7280] mt-1">
              Upload → Gemini Extract → Deterministic Rules R1–R5
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
          <div className="p-3.5 rounded-lg border border-gray-200 bg-[#FAFAFA] space-y-2 text-xs">
            <div className="flex items-center justify-between font-medium text-[#111827]">
              <span>Pipeline Status</span>
              <span className="font-mono uppercase text-[11px] text-[#6B7280]">{step}</span>
            </div>
            {["uploading", "extracting", "detecting"].includes(step) && (
              <div className="flex items-center gap-2 text-[#6B7280]">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
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
                  <span>
                    Batch {result.upload.batch_id} complete ({result.extract.rows_extracted} rows via{" "}
                    {result.extract.model}, {result.detect.findings_created} findings).
                  </span>
                </div>
                {result.extract.verification_warnings?.length > 0 && (
                  <p className="text-[#6B7280] flex items-center gap-1">
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
            className="px-3.5 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium text-gray-700"
          >
            Close
          </button>
          <button
            type="submit"
            disabled={!file || ["uploading", "extracting", "detecting"].includes(step)}
            className="px-3.5 py-1.5 rounded-lg bg-[#111827] hover:bg-gray-800 text-white text-xs font-medium disabled:opacity-50"
          >
            Upload &amp; Run Audit
          </button>
        </div>
      </form>
    </Modal>
  );
}
