"""BNPL fast path: one bounded reasoning-agent call plus deterministic scoring.

The agent assesses evidence quality and uncertainty in a single structured response.
It never owns the final outcome: eligibility, hard rules, weights, and thresholds stay
in Python. A missing/late agent response cannot produce an automatic approval.
"""

import asyncio
import json
import time
from typing import Any

from app.agents.prompts import BNPL_REASONING_SYSTEM_PROMPT
from app.agents.subagents import get_bnpl_reasoning_agent
from app.config import BNPL_AGENT_TIMEOUT_MS
from app.ledger import new_decision_id, save_decision
from app.models import AgentMessage, BnplReasoningAssessment, DecisionLineage, DecisionRecord
from app.tools import scoring
from app.tools.evidence import build_flat_evidence, fetch_full_packet, mask_pii
from app.tools.explanation import generate_template_explanation
from app.tools.policy import get_active_policy, get_segment_config

PRODUCT = "bnpl"
CHECKOUT_RESERVE_MS = 150


def _source_quality(packet: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        source: {
            "confidence": evidence.get("confidence", "missing"),
            "freshness_days": evidence.get("freshness_days"),
        }
        for source, evidence in packet.items()
    }


async def _run_bnpl_reasoning(payload: dict[str, Any]) -> BnplReasoningAssessment:
    return await get_bnpl_reasoning_agent().ainvoke(
        [
            {"role": "system", "content": BNPL_REASONING_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, separators=(",", ":"), default=str)},
        ]
    )


async def decide_bnpl(applicant_id: str) -> DecisionRecord:
    start = time.perf_counter()
    timing_ms: dict[str, float] = {}
    degradations: list[str] = []
    agent_messages: list[AgentMessage] = []

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
    hard_rules_triggered = scoring.evaluate_hard_rules(flat_evidence, segment_cfg, segment_cfg["hard_rules"], PRODUCT)
    dti = scoring.compute_dti(
        flat_evidence["monthly_income"],
        flat_evidence["monthly_obligations"],
        segment_cfg["affordability"]["dti_decline_ceiling"],
    )
    risk_anchor = scoring.compute_risk_anchor(flat_evidence["max_dpd"], flat_evidence["utilization_ratio"])
    timing_ms["deterministic_anchors"] = round((time.perf_counter() - t) * 1000, 2)

    agent_assessment: BnplReasoningAssessment | None = None
    agent_status = "completed"
    checkout_budget_ms = segment_cfg.get("time_budget_ms", 2000)
    elapsed_ms = (time.perf_counter() - start) * 1000
    remaining_agent_ms = max(1, checkout_budget_ms - CHECKOUT_RESERVE_MS - elapsed_ms)
    policy_agent_timeout_ms = segment_cfg.get("agent", {}).get("timeout_ms", BNPL_AGENT_TIMEOUT_MS)
    agent_timeout_ms = min(BNPL_AGENT_TIMEOUT_MS, policy_agent_timeout_ms, remaining_agent_ms)

    safe_packet = mask_pii(packet)
    for source_evidence in safe_packet.values():
        source_evidence.pop("applicant_id", None)

    reasoning_payload = {
        "evidence": safe_packet,
        "source_quality": _source_quality(packet),
        "eligibility": eligibility,
        "hard_rule_hits": [
            {"id": rule["id"], "condition": rule["condition"], "action": rule["action"]}
            for rule in hard_rules_triggered
        ],
        "anchors": {"affordability": dti, "risk": risk_anchor},
        "policy": {
            "dti_decline_ceiling": segment_cfg["affordability"]["dti_decline_ceiling"],
            "max_bnpl_stacking": segment_cfg["risk"]["max_bnpl_stacking"],
            "max_utilization": segment_cfg["risk"]["max_utilization"],
        },
    }

    t = time.perf_counter()
    try:
        agent_assessment = await asyncio.wait_for(
            _run_bnpl_reasoning(reasoning_payload),
            timeout=agent_timeout_ms / 1000,
        )
        agent_messages.append(
            AgentMessage(
                from_agent="bnpl",
                message_type="assessment",
                content=(
                    f"affordability={agent_assessment.affordability}, risk={agent_assessment.risk}, "
                    f"confidence={agent_assessment.confidence:.2f}: {agent_assessment.reasoning}"
                ),
                evidence_refs=agent_assessment.evidence_refs,
            )
        )
    except TimeoutError:
        agent_status = "timeout"
        degradations.append(f"bnpl_agent_timeout: exceeded {agent_timeout_ms:.0f}ms deadline")
    except Exception as exc:  # noqa: BLE001 — safe REFER fallback is intentional for provider/schema failures
        agent_status = "error"
        degradations.append(f"bnpl_agent_unavailable ({type(exc).__name__}): safe fallback applied")
    timing_ms["agent_reasoning"] = round((time.perf_counter() - t) * 1000, 2)

    t = time.perf_counter()
    component_scores: dict[str, float] | None = None
    final_score: float | None = None
    decisive_factors: list[str] = []

    if eligibility["result"] == "FAIL":
        outcome, reason_code = "DECLINE", "BELOW_MINIMUM_CREDIT_PROFILE"
        decisive_factors = eligibility["reasons"]
    elif hard_rules_triggered:
        rule = hard_rules_triggered[0]
        outcome, reason_code = rule["action"], rule["reason_code"]
        decisive_factors = [f"hard rule {rule['id']}: {rule['condition']}"]
    elif agent_assessment is None:
        outcome, reason_code = "REFER", "AGENT_REASONING_UNAVAILABLE"
        decisive_factors = ["BNPL reasoning agent did not complete within the checkout deadline"]
    elif agent_assessment.confidence < segment_cfg.get("agent", {}).get("min_confidence", 0.6):
        outcome, reason_code = "REFER", "AGENT_LOW_CONFIDENCE"
        decisive_factors = [
            f"BNPL agent confidence {agent_assessment.confidence:.2f} is below the automation minimum",
            *agent_assessment.flags[:2],
        ]
    else:
        component_scores = {"eligibility": 1.0, "affordability": dti["suggested_score"], "risk": risk_anchor["suggested_score"]}
        final_score = scoring.compute_weighted_score(
            1.0,
            dti["suggested_score"],
            risk_anchor["suggested_score"],
            segment_cfg["scoring"]["weights"],
        )
        outcome = scoring.apply_thresholds(final_score, segment_cfg["scoring"]["thresholds"])
        reason_code = {"APPROVE": "SCORE_ABOVE_THRESHOLD", "DECLINE": "SCORE_BELOW_THRESHOLD", "REFER": "SCORE_IN_REFER_BAND"}[outcome]
        decisive_factors = [
            f"affordability band: {dti['band']}",
            f"risk band: {risk_anchor['band']}",
            f"BNPL agent confidence: {agent_assessment.confidence:.2f}",
        ]
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
        bnpl_reasoning_assessment=agent_assessment.model_dump() if agent_assessment else None,
        agent_reasoning_status=agent_status,
        component_scores=component_scores,
        final_score=final_score,
        thresholds=segment_cfg["scoring"]["thresholds"],
        decisive_factors=decisive_factors,
        agent_messages=agent_messages,
        evidence_snapshot=flat_evidence,
        timing_ms=timing_ms,
        degradations=degradations,
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
