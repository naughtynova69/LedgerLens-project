import React from "react";
import { ExternalLink, FileSpreadsheet, FileText, Image as ImageIcon } from "lucide-react";

const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"];

function detectPreviewKind(fileName = "", mimeType = "") {
  const lowerName = (fileName || "").toLowerCase();
  const lowerMime = (mimeType || "").toLowerCase();

  if (lowerMime.includes("csv") || lowerName.endsWith(".csv")) {
    return "csv";
  }
  if (lowerMime === "application/pdf" || lowerMime.includes("pdf") || lowerName.endsWith(".pdf")) {
    return "pdf";
  }
  if (
    lowerMime.startsWith("image/") ||
    IMAGE_EXTENSIONS.some((ext) => lowerName.endsWith(ext))
  ) {
    return "image";
  }
  return "unsupported";
}

export function PdfEvidencePreview({ batchId, fileName, mimeType }) {
  if (!batchId || (!fileName && !mimeType)) {
    return (
      <div className="bg-slate-50 border border-[#E2E8F0] rounded-md p-6 text-center h-[calc(100vh-280px)] min-h-[360px] max-h-[540px] flex flex-col items-center justify-center">
        <FileText className="w-6 h-6 text-slate-400 mb-2" />
        <p className="text-xs font-medium text-slate-900">No source document attached</p>
        <p className="text-[11px] text-slate-500 mt-1 max-w-xs">
          Upload a PDF or scanned invoice image to inspect side-by-side evidence.
        </p>
      </div>
    );
  }

  const kind = detectPreviewKind(fileName, mimeType);
  const fileUrl = `/api/batches/${batchId}/file`;

  if (kind === "csv") {
    return (
      <div className="bg-slate-50 border border-[#E2E8F0] rounded-md p-6 text-center h-[calc(100vh-280px)] min-h-[360px] max-h-[540px] flex flex-col items-center justify-center">
        <FileSpreadsheet className="w-6 h-6 text-slate-400 mb-2" />
        <p className="text-xs font-medium text-slate-900">
          Tabular CSV batch ({fileName || "data.csv"})
        </p>
        <p className="text-[11px] text-slate-500 mt-1 max-w-xs">
          Inline document preview is shown for PDF and scanned invoice image batches.
        </p>
      </div>
    );
  }

  if (kind === "unsupported") {
    return (
      <div className="bg-slate-50 border border-[#E2E8F0] rounded-md p-6 text-center h-[calc(100vh-280px)] min-h-[360px] max-h-[540px] flex flex-col items-center justify-center space-y-2">
        <FileText className="w-6 h-6 text-slate-400" />
        <p className="text-xs font-medium text-slate-900">
          Preview unavailable for {fileName || mimeType}
        </p>
        <a
          href={fileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs font-medium text-slate-900 underline hover:text-slate-700"
        >
          Open source file
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-[#E2E8F0] bg-[#F8FAFC]">
        <div className="flex items-center gap-2 min-w-0">
          {kind === "pdf" ? (
            <FileText className="w-3.5 h-3.5 text-[#B91C1C] shrink-0" />
          ) : (
            <ImageIcon className="w-3.5 h-3.5 text-slate-600 shrink-0" />
          )}
          <span className="text-xs font-medium text-slate-900 truncate">
            {fileName || (kind === "pdf" ? "Invoice Document.pdf" : "Invoice Image")}
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-100 text-slate-600 border border-[#E2E8F0]">
            {kind}
          </span>
        </div>

        <a
          href={fileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 hover:text-slate-900 shrink-0"
        >
          Open
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      <div className="p-2.5 bg-slate-50 h-[calc(100vh-280px)] min-h-[360px] max-h-[540px] flex items-center justify-center">
        {kind === "pdf" ? (
          <iframe
            src={fileUrl}
            title={fileName || `Batch ${batchId} PDF evidence`}
            className="w-full h-full rounded border border-[#E2E8F0] bg-white"
          />
        ) : (
          <img
            src={fileUrl}
            alt={fileName || `Batch ${batchId} image evidence`}
            className="max-h-full max-w-full mx-auto rounded border border-[#E2E8F0] bg-white object-contain"
          />
        )}
      </div>
    </div>
  );
}
