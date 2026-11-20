/**
 * Financial and date formatting helpers for LedgerLens
 */

const CURRENCY_SYMBOLS = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

export function formatCurrency(amount, currency = "INR") {
  const numeric = typeof amount === "number" ? amount : parseFloat(amount || 0);
  if (isNaN(numeric)) return "₹0.00";

  const curr = (currency || "INR").toUpperCase();
  const symbol = CURRENCY_SYMBOLS[curr] || `${curr} `;

  const parts = Math.abs(numeric).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const prefix = numeric < 0 ? "-" : "";
  return `${prefix}${symbol}${parts}`;
}

export function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function formatConfidence(score) {
  const num = typeof score === "number" ? score : parseFloat(score || 0);
  if (isNaN(num)) return "0%";
  return `${Math.round(num * 100)}%`;
}

export function formatNumber(val) {
  const num = typeof val === "number" ? val : parseFloat(val || 0);
  if (isNaN(num)) return "0";
  return num.toLocaleString();
}
