"""Rule registry: rules self-register via @register("Rx") and run_all executes them all."""
from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, replace
from typing import Any, Callable

from .types import Finding

DEFAULT_FX_RATES: dict[str, float] = {
    "INR": 1.0,
    "USD": 88.0,
    "EUR": 95.0,
    "GBP": 112.0,
}


@dataclass
class DetectionContext:
    """Normalized records handed to every rule. Rows are plain dicts whose keys
    match the column dictionaries in docs/03_DATA_MODEL.md."""

    invoices: list = field(default_factory=list)        # one dict per invoice LINE
    payments: list = field(default_factory=list)
    purchase_orders: list = field(default_factory=list)
    contracts: list = field(default_factory=list)
    vendors: list = field(default_factory=list)
    goods_receipts: list = field(default_factory=list)
    policy: dict = field(default_factory=dict)


DETECTORS: dict[str, Callable[[DetectionContext], list[Finding]]] = {}


def register(rule_id: str) -> Callable:
    """Class decorator registering a detector under its rule ID (R1..R7)."""

    def decorator(fn: Callable[[DetectionContext], list[Finding]]):
        DETECTORS[rule_id] = fn
        return fn

    return decorator


def _effective_fx_rates(policy: dict[str, Any]) -> dict[str, float]:
    rates = dict(DEFAULT_FX_RATES)
    override = policy.get("fx_rates")
    if isinstance(override, dict):
        for curr, rate in override.items():
            try:
                val = float(rate)
            except (TypeError, ValueError):
                continue
            if val > 0:
                rates[str(curr).strip().upper()] = val
    return rates


def _apply_auto_hold_policy(findings: list[Finding], policy: dict[str, Any]) -> None:
    """Escalate eligible findings to HOLD_PAYMENT when amount_at_risk meets auto_hold_threshold_inr."""
    raw_threshold = policy.get("auto_hold_threshold_inr")
    if raw_threshold is None:
        return
    try:
        threshold_inr = float(raw_threshold)
    except (TypeError, ValueError):
        return
    if threshold_inr <= 0:
        return

    fx_rates = _effective_fx_rates(policy)
    for f in findings:
        curr = str(f.currency or "INR").strip().upper()
        rate = fx_rates.get(curr, 1.0)
        amount_inr = float(f.amount_at_risk or 0.0) * rate
        if amount_inr >= threshold_inr and f.recommended_action == "DISPUTE_VENDOR":
            f.recommended_action = "HOLD_PAYMENT"
            if isinstance(f.proof_trail, dict):
                f.proof_trail["recommended_action"] = "HOLD_PAYMENT"
                math_block = f.proof_trail.setdefault("math", {})
                if isinstance(math_block, dict):
                    math_block["auto_hold_triggered"] = True
                    math_block["auto_hold_threshold_inr"] = threshold_inr


def run_all_rules(ctx: DetectionContext, policy: dict | None = None) -> list[Finding]:
    """Run every registered rule in stable order, honoring optional policy overrides."""
    base_policy = ctx.get("policy", {}) if isinstance(ctx, dict) else (getattr(ctx, "policy", None) or {})
    merged_policy = dict(base_policy)
    if policy:
        merged_policy.update(policy)

    if is_dataclass(ctx):
        effective_ctx: Any = replace(ctx, policy=merged_policy)
    elif isinstance(ctx, dict):
        effective_ctx = {**ctx, "policy": merged_policy}
    else:
        effective_ctx = ctx

    findings: list[Finding] = []
    for rule_id in sorted(DETECTORS):
        findings.extend(DETECTORS[rule_id](effective_ctx))

    if merged_policy:
        _apply_auto_hold_policy(findings, merged_policy)

    return findings


def run_all(ctx: DetectionContext, policy: dict | None = None) -> list[Finding]:
    """Backward-compatible alias for run_all_rules."""
    return run_all_rules(ctx, policy=policy)
