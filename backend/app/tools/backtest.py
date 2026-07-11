"""Policy back-test against the synthetic historic-outcomes book.

Replays every historic applicant through the deterministic decision path (eligibility ->
hard rules -> anchor scores -> weighted score -> thresholds) under the active policy and a
draft, then compares approval rate, realized bad rate among approvals, and expected loss.
Also buckets the book by predicted score to show a calibration curve (predicted risk vs
actual default rate). Entirely deterministic — no LLM in this path.
"""

import json
from typing import Any

from app.config import POLICY_DRAFTS_ROOT, WORKSPACE_ROOT
from app.tools import scoring
from app.tools.policy import get_active_policy, get_segment_config, load_policy_file, _recompute_decision

HISTORY_BOOK_PATH = WORKSPACE_ROOT / "history" / "historic_outcomes.json"

_CALIBRATION_BUCKETS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]


def load_history_book() -> dict[str, Any]:
    if not HISTORY_BOOK_PATH.exists():
        raise FileNotFoundError(
            f"Historic book not found at {HISTORY_BOOK_PATH}. Run scripts/generate_history_book.py first."
        )
    return json.loads(HISTORY_BOOK_PATH.read_text())


def _replay_book(records: list[dict], segment_cfg: dict, product: str, lgd: float) -> dict[str, Any]:
    """Run every historic record through the deterministic decision path under one policy."""
    outcomes = {"APPROVE": 0, "DECLINE": 0, "REFER": 0}
    reason_codes: dict[str, int] = {}
    approved_defaults = 0
    expected_loss = 0.0
    decisions = []

    for record in records:
        result = _recompute_decision(record["features"], segment_cfg, product, None)
        outcomes[result["outcome"]] += 1
        reason_codes[result["reason_code"]] = reason_codes.get(result["reason_code"], 0) + 1
        if result["outcome"] == "APPROVE":
            if record["outcome"] == "default":
                approved_defaults += 1
                expected_loss += record["features"]["total_exposure"] * lgd
        decisions.append(result)

    total = len(records)
    approved = outcomes["APPROVE"]
    return {
        "total": total,
        "approval_rate": round(approved / total, 4),
        "decline_rate": round(outcomes["DECLINE"] / total, 4),
        "refer_rate": round(outcomes["REFER"] / total, 4),
        "approved_count": approved,
        "approved_defaults": approved_defaults,
        "bad_rate_among_approved": round(approved_defaults / approved, 4) if approved else None,
        "expected_loss": round(expected_loss, 2),
        "reason_codes": dict(sorted(reason_codes.items(), key=lambda kv: -kv[1])),
        "_decisions": decisions,
    }


def _calibration_curve(records: list[dict], segment_cfg: dict) -> list[dict[str, Any]]:
    """Score the FULL book with the weighted model (no rule short-circuits) and report the
    actual default rate per predicted-score bucket — does the score rank risk correctly?
    """
    scored = []
    for record in records:
        f = record["features"]
        dti = scoring.compute_dti(f["monthly_income"], f["monthly_obligations"], segment_cfg["affordability"]["dti_decline_ceiling"])
        risk_anchor = scoring.compute_risk_anchor(f["max_dpd"], f["utilization_ratio"])
        score = scoring.compute_weighted_score(1.0, dti["suggested_score"], risk_anchor["suggested_score"], segment_cfg["scoring"]["weights"])
        scored.append((score, record["outcome"] == "default"))

    buckets = []
    for low, high in _CALIBRATION_BUCKETS:
        members = [is_default for score, is_default in scored if low <= score < high]
        buckets.append(
            {
                "score_range": f"{'<0.5' if low == 0.0 else f'{low:.1f}–{min(high, 1.0):.1f}'}",
                "count": len(members),
                "actual_default_rate": round(sum(members) / len(members), 4) if members else None,
            }
        )
    return buckets


def backtest_policy_change(draft_filename: str, product: str) -> dict[str, Any]:
    """Replay the historic book under active vs draft policy; return the risk trade-off."""
    book = load_history_book()
    records = book["records"]
    lgd = book["meta"]["lgd"]

    active_policy = get_active_policy()
    draft_policy = load_policy_file(POLICY_DRAFTS_ROOT / draft_filename)

    active_segment = get_segment_config(active_policy, product)
    active = _replay_book(records, active_segment, product, lgd)
    draft = _replay_book(records, get_segment_config(draft_policy, product), product, lgd)

    calibration = _calibration_curve(records, active_segment)
    active.pop("_decisions")
    draft.pop("_decisions")

    def _delta(key: str):
        a, d = active.get(key), draft.get(key)
        return round(d - a, 4) if isinstance(a, (int, float)) and isinstance(d, (int, float)) else None

    return {
        "book": {k: book["meta"][k] for k in ("size", "seed", "base_default_rate", "lgd", "caveat")},
        "product": product,
        "active_version": active_policy["version"],
        "draft_version": draft_policy["version"],
        "active": active,
        "draft": draft,
        "deltas": {
            "approval_rate": _delta("approval_rate"),
            "bad_rate_among_approved": _delta("bad_rate_among_approved"),
            "expected_loss": _delta("expected_loss"),
            "approved_count": _delta("approved_count"),
        },
        "calibration": calibration,
    }
