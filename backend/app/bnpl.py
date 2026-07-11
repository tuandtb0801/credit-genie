"""BNPL fast path: pure deterministic Python, zero LLM calls, budget < 2s.

docs/decision-modes-and-controls.md section 1.2 explicitly rules out an LLM in the
BNPL request path even though the low-level sequence diagram shows one orchestration
call — this module resolves that in favor of the stricter, latency-safe reading.
"""

import time

from app.ledger import new_decision_id, save_decision
from app.models import DecisionLineage, DecisionRecord
from app.tools import scoring
from app.tools.evidence import build_flat_evidence, fetch_full_packet
from app.tools.explanation import generate_template_explanation
from app.tools.policy import get_active_policy, get_segment_config

PRODUCT = "bnpl"


def decide_bnpl(applicant_id: str) -> DecisionRecord:
    start = time.perf_counter()
    timing_ms: dict[str, float] = {}

    t = time.perf_counter()
    packet = fetch_full_packet(applicant_id)
    flat_evidence = build_flat_evidence(packet)
    timing_ms["ingest"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    policy = get_active_policy()
    segment_cfg = get_segment_config(policy, PRODUCT)
    timing_ms["policy_load"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    eligibility = scoring.eligibility_check(flat_evidence, segment_cfg)
    hard_rules_triggered: list[dict] = []
    component_scores: dict[str, float] | None = None
    final_score: float | None = None
    decisive_factors: list[str] = []

    if eligibility["result"] == "FAIL":
        outcome, reason_code = "DECLINE", "BELOW_MINIMUM_CREDIT_PROFILE"
        decisive_factors = eligibility["reasons"]
    else:
        hard_rules_triggered = scoring.evaluate_hard_rules(flat_evidence, segment_cfg, segment_cfg["hard_rules"], PRODUCT)
        if hard_rules_triggered:
            rule = hard_rules_triggered[0]
            outcome, reason_code = rule["action"], rule["reason_code"]
            decisive_factors = [f"hard rule {rule['id']}: {rule['condition']}"]
        else:
            dti = scoring.compute_dti(flat_evidence["monthly_income"], flat_evidence["monthly_obligations"], segment_cfg["affordability"]["dti_decline_ceiling"])
            risk_anchor = scoring.compute_risk_anchor(flat_evidence["max_dpd"], flat_evidence["utilization_ratio"])
            component_scores = {"eligibility": 1.0, "affordability": dti["suggested_score"], "risk": risk_anchor["suggested_score"]}
            final_score = scoring.compute_weighted_score(1.0, dti["suggested_score"], risk_anchor["suggested_score"], segment_cfg["scoring"]["weights"])
            outcome = scoring.apply_thresholds(final_score, segment_cfg["scoring"]["thresholds"])
            reason_code = {"APPROVE": "SCORE_ABOVE_THRESHOLD", "DECLINE": "SCORE_BELOW_THRESHOLD", "REFER": "SCORE_IN_REFER_BAND"}[outcome]
            decisive_factors = [f"affordability band: {dti['band']}", f"risk band: {risk_anchor['band']}"]
    timing_ms["rules_and_score"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    template_fields = {
        **flat_evidence,
        "dti_decline_ceiling": segment_cfg["affordability"]["dti_decline_ceiling"],
        "approve_threshold": segment_cfg["scoring"]["thresholds"]["approve"],
        "decline_threshold": segment_cfg["scoring"]["thresholds"]["decline"],
        "final_score": final_score or 0.0,
        "eligibility_score": (component_scores or {}).get("eligibility", 0.0),
        "affordability_score": (component_scores or {}).get("affordability", 0.0),
        "risk_score": (component_scores or {}).get("risk", 0.0),
    }
    explanation = generate_template_explanation(reason_code, template_fields)
    timing_ms["explain"] = round((time.perf_counter() - t) * 1000, 2)

    lineage = DecisionLineage(
        applicant_id=applicant_id,
        product=PRODUCT,
        policy_version=policy["version"],
        policy_hash=policy["_hash"],
        eligibility_result=eligibility,
        hard_rules_triggered=hard_rules_triggered,
        component_scores=component_scores,
        final_score=final_score,
        thresholds=segment_cfg["scoring"]["thresholds"],
        decisive_factors=decisive_factors,
        evidence_snapshot=flat_evidence,
        timing_ms=timing_ms,
    )

    record = DecisionRecord(
        decision_id=new_decision_id(),
        applicant_id=applicant_id,
        product=PRODUCT,
        outcome=outcome,
        reason_code=reason_code,
        lineage=lineage,
        explanation=explanation,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )
    return save_decision(record)
