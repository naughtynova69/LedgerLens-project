import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import { formatCurrency } from "../utils/formatters";

const SERVICE_LABELS = [
  { key: "bigquery", label: "BigQuery" },
  { key: "alloydb", label: "AlloyDB" },
  { key: "cloud_storage", label: "Cloud Storage" },
  { key: "vertex_ai", label: "Vertex AI" },
  { key: "secret_manager", label: "Secret Manager" },
  { key: "pubsub", label: "Pub/Sub" },
];

const RULES_SUMMARY = [
  {
    id: "R1",
    name: "Duplicate & Near-Duplicate Invoices",
    desc: "Detects alphanumeric invoice variants, date proximity, line similarity, and same-PO double billing.",
  },
  {
    id: "R2",
    name: "Contract Price Leakage",
    desc: "Flags unit prices above negotiated contract terms or missed contractual discounts.",
  },
  {
    id: "R3",
    name: "PO Mismatch & Overbilling",
    desc: "Catches cumulative billed quantities exceeding PO limits, premature billing, or unordered items.",
  },
  {
    id: "R4",
    name: "Currency, FX & Tax Errors",
    desc: "Flags currency mismatches, FX drift beyond tolerance, tax on exempt contracts, and duplicate tax lines.",
  },
  {
    id: "R5",
    name: "Cancelled-Service Leakage",
    desc: "Detects charges billed after contract cancellation, expiry, or inactive vendor/PO status.",
  },
];

export function CloudIntegrationsView({
  executiveAnalytics,
  onRefreshAnalytics,
  onToast,
}) {
  const [gcpStatus, setGcpStatus] = useState(null);
  const [localAnalytics, setLocalAnalytics] = useState(executiveAnalytics);
  const [syncingBq, setSyncingBq] = useState(false);
  const [syncResult, setSyncResult] = useState(null);

  const [policy, setPolicy] = useState({
    r1_max_amount_drift_pct: 0.5,
    r1_max_date_gap_days: 30,
    r4_max_fx_drift_pct: 2.0,
    auto_hold_threshold_inr: 10000,
  });
  const [savingPolicy, setSavingPolicy] = useState(false);

  const loadCloudAndPolicy = useCallback(async () => {
    const [gcp, pol, analytics] = await Promise.all([
      api.getGcpStatus().catch(() => null),
      api.getPolicy().catch(() => null),
      executiveAnalytics
        ? Promise.resolve(executiveAnalytics)
        : api.getExecutiveAnalytics().catch(() => null),
    ]);
    if (gcp) setGcpStatus(gcp);
    if (pol) setPolicy(pol);
    if (analytics) setLocalAnalytics(analytics);
  }, [executiveAnalytics]);

  useEffect(() => {
    loadCloudAndPolicy();
  }, [loadCloudAndPolicy]);

  useEffect(() => {
    if (executiveAnalytics) {
      setLocalAnalytics(executiveAnalytics);
    }
  }, [executiveAnalytics]);

  const handleSyncBigQuery = async () => {
    setSyncingBq(true);
    try {
      const res = await api.syncBigQuery();
      setSyncResult(res);
      if (onRefreshAnalytics) {
        await onRefreshAnalytics();
      }
      if (onToast) {
        onToast(
          res.synced
            ? `Synced ${res.total_rows_synced ?? res.total_rows_prepared} rows to BigQuery (${res.dataset}).`
            : `Prepared ${res.total_rows_prepared ?? 0} rows in local BigQuery simulation (${res.dataset}).`,
          "success",
          "BigQuery Sync Complete"
        );
      }
    } catch (err) {
      if (onToast) {
        onToast(err.message || "BigQuery sync failed.", "error", "BigQuery Sync Failed");
      }
    } finally {
      setSyncingBq(false);
    }
  };

  const handlePolicyChange = (key, value) => {
    setPolicy((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSavePolicy = async (e) => {
    e.preventDefault();
    setSavingPolicy(true);
    try {
      const payload = {
        r1_max_amount_drift_pct: Number(policy.r1_max_amount_drift_pct),
        r1_max_date_gap_days: parseInt(policy.r1_max_date_gap_days, 10),
        r4_max_fx_drift_pct: Number(policy.r4_max_fx_drift_pct),
        auto_hold_threshold_inr: Number(policy.auto_hold_threshold_inr),
      };
      const updated = await api.updatePolicy(payload);
      setPolicy(updated);
      if (onToast) {
        onToast("Policy thresholds updated and logged.", "success", "Policy Saved");
      }
    } catch (err) {
      if (onToast) {
        onToast(err.message || "Failed to update policy.", "error", "Policy Save Failed");
      }
    } finally {
      setSavingPolicy(false);
    }
  };

  const services = gcpStatus?.services || {};
  const topVendors = localAnalytics?.top_vendors || [];

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-[#111827] tracking-tight">
            Cloud &amp; Policy
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Google Cloud infrastructure status, BigQuery warehouse sync, vendor exposure, and rule thresholds
          </p>
        </div>
        {gcpStatus && (
          <div className="text-xs font-mono text-[#6B7280]">
            {gcpStatus.project_id ? `${gcpStatus.project_id} · ${gcpStatus.location}` : `Local mode · ${gcpStatus.location || "asia-south1"}`}
          </div>
        )}
      </div>

      {/* Google Cloud Service Status Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {SERVICE_LABELS.map(({ key, label }) => {
          const svc = services[key];
          const isConnected = svc?.mode === "configured";
          return (
            <div
              key={key}
              className="bg-white border border-gray-200 rounded-lg p-4 flex items-start justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="text-xs font-semibold text-[#111827]">{label}</div>
                <div
                  className="text-[11px] font-mono text-[#6B7280] truncate mt-1"
                  title={svc?.target || ""}
                >
                  {svc?.target || "local_fallback"}
                </div>
              </div>
              <span
                className={`shrink-0 px-2 py-0.5 rounded-md text-[11px] font-medium border ${
                  isConnected
                    ? "bg-emerald-50/80 text-emerald-700 border-emerald-200"
                    : "bg-gray-50 text-gray-600 border-gray-200"
                }`}
              >
                {isConnected ? "Connected" : "Local Fallback"}
              </span>
            </div>
          );
        })}
      </div>

      {/* BigQuery Sync & Top Vendors by Exposure */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* BigQuery Sync Card */}
        <div className="lg:col-span-5 bg-white border border-gray-200 rounded-lg p-5 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-[#111827]">
                BigQuery Warehouse Sync
              </h2>
              <p className="text-xs text-[#6B7280] mt-0.5">
                Push FX-normalized invoices, findings, and audit log events to BigQuery.
              </p>
            </div>
            <button
              type="button"
              onClick={handleSyncBigQuery}
              disabled={syncingBq}
              className="shrink-0 px-3 py-1.5 rounded-lg bg-[#111827] hover:bg-gray-800 text-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              {syncingBq ? "Syncing..." : "Sync to BigQuery"}
            </button>
          </div>

          {syncResult ? (
            <div className="border border-gray-200 rounded-lg bg-[#FAFAFA] p-3.5 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[#6B7280]">Target dataset</span>
                <span className="font-mono font-medium text-[#111827]">
                  {syncResult.project_id
                    ? `${syncResult.project_id}.${syncResult.dataset}`
                    : syncResult.dataset}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#6B7280]">Mode</span>
                <span className="font-mono text-[#111827]">
                  {syncResult.synced ? "BigQuery Live" : "Local Simulation"}
                </span>
              </div>
              <div className="pt-2 border-t border-gray-200 space-y-1 font-mono text-[11px]">
                {Object.entries(syncResult.tables || {}).map(([tableName, count]) => (
                  <div key={tableName} className="flex items-center justify-between">
                    <span className="text-[#6B7280]">{tableName}</span>
                    <span className="tabular-nums text-[#111827]">{count} rows</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="border border-gray-200 rounded-lg bg-[#FAFAFA] px-3.5 py-3 text-xs text-[#6B7280]">
              Dataset target:{" "}
              <span className="font-mono text-[#111827]">
                {services.bigquery?.target || "ledgerlens_analytics"}
              </span>
            </div>
          )}
        </div>

        {/* Top Vendors by Exposure Table */}
        <div className="lg:col-span-7 bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#111827]">
              Top Vendors by Exposure (INR Eq.)
            </h2>
            {localAnalytics && (
              <span className="text-xs font-mono tabular-nums text-[#6B7280]">
                Leakage: {localAnalytics.leakage_pct_of_spend ?? 0}% of spend
              </span>
            )}
          </div>

          {topVendors.length === 0 ? (
            <div className="p-6 text-center text-xs text-[#6B7280]">
              No vendor exposure analytics available yet. Load demo data or ingest invoices.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAFAFA] border-b border-gray-200 text-[#6B7280]">
                  <tr>
                    <th className="py-2 px-4 font-medium">Vendor</th>
                    <th className="py-2 px-3 font-medium text-right">Findings</th>
                    <th className="py-2 px-3 font-medium text-right">At Risk (INR)</th>
                    <th className="py-2 px-3 font-medium text-right">Open (INR)</th>
                    <th className="py-2 px-4 font-medium text-right">Recovered (INR)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {topVendors.map((v) => (
                    <tr key={v.vendor_id} className="hover:bg-gray-50/70">
                      <td className="py-2.5 px-4">
                        <div className="font-medium text-[#111827]">{v.vendor_name}</div>
                        <div className="font-mono text-[11px] text-[#6B7280]">
                          {v.vendor_id}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-[#111827]">
                        {v.finding_count}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums font-medium text-[#B91C1C]">
                        {formatCurrency(v.amount_at_risk_inr, "INR")}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums text-[#6B7280]">
                        {formatCurrency(v.open_inr, "INR")}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums font-medium text-[#047857]">
                        {formatCurrency(v.recovered_inr, "INR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Policy Thresholds Form */}
      <form
        onSubmit={handleSavePolicy}
        className="bg-white border border-gray-200 rounded-lg p-5 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-[#111827]">Policy Thresholds</h2>
            <p className="text-xs text-[#6B7280] mt-0.5">
              Deterministic tolerance thresholds governing duplicate detection, FX variance, and payment holds
            </p>
          </div>
          <button
            type="submit"
            disabled={savingPolicy}
            className="self-start sm:self-auto px-3.5 py-1.5 rounded-lg bg-[#111827] hover:bg-gray-800 text-white text-xs font-medium transition-colors disabled:opacity-50"
          >
            {savingPolicy ? "Saving..." : "Save Policy"}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label
              htmlFor="policy-r1-drift"
              className="block text-xs font-medium text-[#111827] mb-1"
            >
              R1 Max Amount Drift (%)
            </label>
            <input
              id="policy-r1-drift"
              type="number"
              step="0.1"
              min="0"
              value={policy.r1_max_amount_drift_pct}
              onChange={(e) => handlePolicyChange("r1_max_amount_drift_pct", e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono tabular-nums text-[#111827] focus:outline-none focus:border-gray-400"
            />
          </div>

          <div>
            <label
              htmlFor="policy-r1-days"
              className="block text-xs font-medium text-[#111827] mb-1"
            >
              R1 Max Date Gap (Days)
            </label>
            <input
              id="policy-r1-days"
              type="number"
              step="1"
              min="0"
              value={policy.r1_max_date_gap_days}
              onChange={(e) => handlePolicyChange("r1_max_date_gap_days", e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono tabular-nums text-[#111827] focus:outline-none focus:border-gray-400"
            />
          </div>

          <div>
            <label
              htmlFor="policy-r4-fx"
              className="block text-xs font-medium text-[#111827] mb-1"
            >
              R4 Max FX Drift (%)
            </label>
            <input
              id="policy-r4-fx"
              type="number"
              step="0.1"
              min="0"
              value={policy.r4_max_fx_drift_pct}
              onChange={(e) => handlePolicyChange("r4_max_fx_drift_pct", e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono tabular-nums text-[#111827] focus:outline-none focus:border-gray-400"
            />
          </div>

          <div>
            <label
              htmlFor="policy-auto-hold"
              className="block text-xs font-medium text-[#111827] mb-1"
            >
              Auto-Hold Threshold (INR)
            </label>
            <input
              id="policy-auto-hold"
              type="number"
              step="100"
              min="0"
              value={policy.auto_hold_threshold_inr}
              onChange={(e) => handlePolicyChange("auto_hold_threshold_inr", e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-mono tabular-nums text-[#111827] focus:outline-none focus:border-gray-400"
            />
          </div>
        </div>
      </form>

      {/* Collapsible R1-R5 Rules Summary */}
      <details className="bg-white border border-gray-200 rounded-lg p-5 group">
        <summary className="cursor-pointer text-xs font-medium text-[#111827] select-none list-none flex items-center justify-between">
          <span>Deterministic Rules Summary (R1–R5)</span>
          <span className="font-mono text-[11px] text-[#6B7280] group-open:hidden">
            Expand
          </span>
          <span className="font-mono text-[11px] text-[#6B7280] hidden group-open:inline">
            Collapse
          </span>
        </summary>

        <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#FAFAFA] border-b border-gray-200 text-[#6B7280]">
              <tr>
                <th className="py-2 px-3 font-medium">Rule</th>
                <th className="py-2 px-3 font-medium">Name</th>
                <th className="py-2 px-3 font-medium">Deterministic Scope</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {RULES_SUMMARY.map((rule) => (
                <tr key={rule.id}>
                  <td className="py-2.5 px-3 font-mono font-medium text-[#111827] whitespace-nowrap">
                    {rule.id}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-[#111827] whitespace-nowrap">
                    {rule.name}
                  </td>
                  <td className="py-2.5 px-3 text-[#6B7280]">{rule.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
