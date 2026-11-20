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
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
        <FileText className="w-6 h-6 text-gray-400 mx-auto mb-2" />
        <p className="text-xs font-medium text-[#111827]">No source document attached</p>
        <p className="text-[11px] text-[#6B7280] mt-1">
          Upload a PDF or scanned invoice image to inspect side-by-side evidence.
        </p>
      </div>
    );
  }

  const kind = detectPreviewKind(fileName, mimeType);
  const fileUrl = `/api/batches/${batchId}/file`;

  if (kind === "csv") {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
        <FileSpreadsheet className="w-6 h-6 text-gray-400 mx-auto mb-2" />
        <p className="text-xs font-medium text-[#111827]">
          Tabular CSV batch ({fileName || "data.csv"})
        </p>
        <p className="text-[11px] text-[#6B7280] mt-1">
          Inline document preview is shown for PDF and scanned invoice image batches.
        </p>
      </div>
    );
  }

  if (kind === "unsupported") {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center space-y-2">
        <FileText className="w-6 h-6 text-gray-400 mx-auto" />
        <p className="text-xs font-medium text-[#111827]">
          Preview unavailable for {fileName || mimeType}
        </p>
        <a
          href={fileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs font-medium text-[#111827] underline hover:text-gray-700"
        >
          Open source file
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-3.5 py-2.5 border-b border-gray-200 bg-slate-50">
        <div className="flex items-center gap-2 min-w-0">
          {kind === "pdf" ? (
            <FileText className="w-4 h-4 text-[#B91C1C] shrink-0" />
          ) : (
            <ImageIcon className="w-4 h-4 text-slate-600 shrink-0" />
          )}
          <span className="text-xs font-medium text-[#111827] truncate">
            {fileName || (kind === "pdf" ? "Invoice Document.pdf" : "Invoice Image")}
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-gray-100 text-[#6B7280] border border-gray-200">
            {kind}
          </span>
        </div>

        <a
          href={fileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#6B7280] hover:text-[#111827] shrink-0"
        >
          Open
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      <div className="p-3 bg-gray-50">
        {kind === "pdf" ? (
          <iframe
            src={fileUrl}
            title={fileName || `Batch ${batchId} PDF evidence`}
            className="w-full h-[460px] rounded border border-gray-200 bg-white"
          />
        ) : (
          <img
            src={fileUrl}
            alt={fileName || `Batch ${batchId} image evidence`}
            className="max-h-[460px] w-auto mx-auto rounded border border-gray-200 bg-white object-contain"
          />
        )}
      </div>
    </div>
  );
}
