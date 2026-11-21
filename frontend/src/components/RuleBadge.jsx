import React from "react";

const RULE_METADATA = {
  R1: {
    label: "Duplicate Bill",
    short: "Duplicate Bill",
  },
  R2: {
    label: "Price Overcharge",
    short: "Price Overcharge",
  },
  R3: {
    label: "PO Mismatch",
    short: "PO Mismatch",
  },
  R4: {
    label: "Tax / Currency Error",
    short: "Tax / Currency",
  },
  R5: {
    label: "Cancelled Service",
    short: "Cancelled Service",
  },
  R6: {
    label: "Split Order",
    short: "Split Order",
  },
  R7: {
    label: "Delivery Mismatch",
    short: "Delivery Mismatch",
  },
  R8: {
    label: "Linked Vendors",
    short: "Linked Vendors",
  },
  R9: {
    label: "Conflict of Interest",
    short: "Conflict of Interest",
  },
  R10: {
    label: "Missing Credit",
    short: "Missing Credit",
  },
};

export function RuleBadge({ ruleId, full = false, className = "" }) {
  const meta = RULE_METADATA[ruleId] || {
    label: ruleId,
    short: ruleId,
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] leading-none font-medium bg-gray-100 text-gray-700 border border-gray-200/80 whitespace-nowrap ${className}`}
      title={`${ruleId}: ${meta.label}`}
    >
      {full ? meta.label : meta.short}
    </span>
  );
}
