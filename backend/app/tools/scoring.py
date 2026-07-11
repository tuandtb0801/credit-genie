"""Deterministic scoring engine. No LLM calls here — agents produce judgment inputs,
this module turns them into the decision via fixed arithmetic and rule matching.
"""

from typing import Any

SCORE_BAND_ORDER = ["poor", "fair", "good", "excellent"]


def rank_score_band(band: str | None) -> int:
    """Map a score band name to its rank (higher is better); unknown bands rank lowest."""
    if band not in SCORE_BAND_ORDER:
        return -1
    return SCORE_BAND_ORDER.index(band)


def eligibility_check(flat_evidence: dict[str, Any], segment_cfg: dict[str, Any]) -> dict[str, Any]:
    """Rules-only gate check. Never uses LLM reasoning — PASS or FAIL, no ambiguity."""
    min_band = segment_cfg["eligibility"]["min_score_band"]
    reasons = []

    if rank_score_band(flat_evidence.get("score_band")) < rank_score_band(min_band):
        reasons.append(f"score_band '{flat_evidence.get('score_band')}' is below minimum '{min_band}'")

    result = "FAIL" if reasons else "PASS"
    return {"result": result, "reasons": reasons, "score_band": flat_evidence.get("score_band")}


_HARD_RULE_NAMES = {"and", "or", "not", "True", "False"}


def _safe_eval_condition(condition: str, flat_evidence: dict[str, Any], segment_cfg: dict[str, Any]) -> bool:
    """Evaluate a policy-authored condition string against evidence + segment config.

    Conditions are authored by policy analysts (same trust boundary as the YAML file
    itself), not end users, so a restricted eval with no builtins is an acceptable way
    to keep hard rules data-driven instead of hard-coded per rule id.
    """
    namespace: dict[str, Any] = dict(flat_evidence)
    for section in ("eligibility", "affordability", "risk"):
        namespace[section] = _AttrDict(segment_cfg.get(section, {}))
    return bool(eval(condition, {"__builtins__": {}}, namespace))  # noqa: S307


class _AttrDict(dict):
    """Dict that also supports attribute access, so 'affordability.dti_decline_ceiling' parses."""

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def evaluate_hard_rules(
    flat_evidence: dict[str, Any],
    segment_cfg: dict[str, Any],
    hard_rules: list[dict[str, Any]],
    product: str,
) -> list[dict[str, Any]]:
    """Evaluate every hard rule that applies to this product, in policy order. First match decides."""
    triggered = []
    for rule in hard_rules:
        if product not in rule.get("applies_to", []):
            continue
        if _safe_eval_condition(rule["condition"], flat_evidence, segment_cfg):
            triggered.append(rule)
    return triggered


def compute_dti(monthly_income: float, monthly_obligations: float, dti_decline_ceiling: float) -> dict[str, Any]:
    """Deterministic DTI calculation and an anchor score/band for the Affordability agent to cite."""
    dti_ratio = (monthly_obligations / monthly_income) if monthly_income else 1.0
    ratio_to_ceiling = dti_ratio / dti_decline_ceiling if dti_decline_ceiling else float("inf")

    if ratio_to_ceiling <= 0.75:
        band, suggested_score = "adequate", 0.85
    elif ratio_to_ceiling <= 1.0:
        band, suggested_score = "marginal", 0.6
    else:
        band, suggested_score = "inadequate", 0.15

    return {
        "dti_ratio": round(dti_ratio, 4),
        "dti_decline_ceiling": dti_decline_ceiling,
        "band": band,
        "suggested_score": suggested_score,
    }


def compute_risk_anchor(max_dpd: int, utilization_ratio: float) -> dict[str, Any]:
    """Deterministic delinquency/exposure severity anchor for the Risk agent to cite."""
    if max_dpd == 0:
        severity = 0
    elif max_dpd < 30:
        severity = 1
    elif max_dpd < 60:
        severity = 2
    elif max_dpd < 90:
        severity = 3
    else:
        severity = 4

    penalty = severity * 0.15 + max(0.0, utilization_ratio - 0.3) * 0.4
    suggested_score = max(0.0, min(0.95, 1.0 - penalty))

    if severity == 0 and utilization_ratio <= 0.3:
        band = "low"
    elif severity <= 1 and utilization_ratio <= 0.6:
        band = "moderate"
    elif severity <= 2 and utilization_ratio <= 0.8:
        band = "elevated"
    else:
        band = "high"

    return {"severity": severity, "band": band, "suggested_score": round(suggested_score, 4)}


def compute_weighted_score(eligibility_score: float, affordability_score: float, risk_score: float, weights: dict[str, float]) -> float:
    """final_score = sum(weight_i * component_score_i). The only place scores get combined."""
    return round(
        eligibility_score * weights["eligibility"]
        + affordability_score * weights["affordability"]
        + risk_score * weights["risk"],
        4,
    )


def apply_thresholds(score: float, thresholds: dict[str, float]) -> str:
    """score >= approve -> APPROVE; score <= decline -> DECLINE; else REFER."""
    if score >= thresholds["approve"]:
        return "APPROVE"
    if score <= thresholds["decline"]:
        return "DECLINE"
    return "REFER"


def check_consensus(
    affordability_score: float,
    risk_score: float,
    affordability_confidence: float,
    risk_confidence: float,
    consensus_cfg: dict[str, float],
) -> dict[str, Any]:
    """Agents must agree in both direction (score gap) and certainty (confidence) to proceed to scoring."""
    score_gap = abs(affordability_score - risk_score)
    min_confidence = min(affordability_confidence, risk_confidence)

    gap_ok = score_gap <= consensus_cfg["max_score_gap"]
    confidence_ok = min_confidence >= consensus_cfg["min_confidence"]

    return {
        "agree": gap_ok and confidence_ok,
        "score_gap": round(score_gap, 4),
        "min_confidence": round(min_confidence, 4),
        "gap_ok": gap_ok,
        "confidence_ok": confidence_ok,
    }
