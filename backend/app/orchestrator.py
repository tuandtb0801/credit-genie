"""Personal Loan full path: the pipeline coordinates deterministically in plain Python
(evidence ingest -> eligibility -> hard rules -> parallel agent assessment -> collaboration
-> consensus -> weighted score -> explanation), while each reasoning step (Affordability,
Risk, Explanation) is a real deepagents/LangGraph agent backed by OpenAI.

Why the orchestration itself isn't an LLM ReAct loop: docs/decision-modes-and-controls.md's
own "Layer 3: Scoring Determinism" requires the weighting, threshold comparison, hard-rule
matching, and consensus check to be deterministic math, not LLM judgment — and the 60s
budget and demo-critical outcomes (e.g. Raj Patel's disagreement -> REFER) need reliable
sequencing. Letting a top-level agent freely decide when to delegate would reintroduce the
non-determinism the docs explicitly rule out. So: Python is the orchestrator; deepagents
provides the reasoning.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from app.agents.prompts import EXPLANATION_SYSTEM_PROMPT
from app.agents.subagents import get_affordability_agent, get_explanation_model, get_risk_agent
from app.ledger import new_decision_id, save_decision
from app.models import AffordabilityAssessment, AgentMessage, DecisionLineage, DecisionRecord, RiskAssessment
from app.tools import scoring
from app.tools.evidence import build_flat_evidence, detect_deposit_irregularity, fetch_full_packet, mask_pii
from app.tools.explanation import generate_template_explanation
from app.tools.policy import get_active_policy, get_segment_config

PRODUCT = "personal_loan"
AGENT_TIMEOUT_S = 25
EXPLAIN_TIMEOUT_S = 30


def _event(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "data": data}


async def _invoke_agent(agent, task_message: str):
    result = await agent.ainvoke({"messages": [{"role": "user", "content": task_message}]})
    return result["structured_response"]


async def _run_affordability(income: dict, irregularity: dict, ceiling: float, concern: str | None = None) -> AffordabilityAssessment:
    message = (
        f"Applicant income evidence (PII-masked): {income}\n"
        f"Deposit pattern observed: {irregularity['pattern']} — {irregularity['note']}\n"
        f"Active policy dti_decline_ceiling for this segment: {ceiling}\n"
    )
    if concern:
        message += f"\nThe Risk agent flagged a concern for you to consider: {concern}\nRe-evaluate with this in mind.\n"
    message += "\nAssess this applicant's affordability."
    return await _invoke_agent(get_affordability_agent(), message)


async def _run_risk(delinquency: dict, exposure: dict, irregularity: dict, employment_type: str, verification_status: str) -> RiskAssessment:
    message = (
        f"Applicant delinquency evidence: {delinquency}\n"
        f"Applicant exposure evidence: {exposure}\n"
        f"Deposit pattern observed in income records: {irregularity['pattern']} — {irregularity['note']}\n"
        f"Employment type: {employment_type}, income verification status: {verification_status}\n\n"
        "Assess this applicant's risk profile."
    )
    return await _invoke_agent(get_risk_agent(), message)


async def decide_personal_loan(applicant_id: str) -> AsyncIterator[dict[str, Any]]:
    start = time.perf_counter()
    timing_ms: dict[str, float] = {}
    degradations: list[str] = []
    agent_messages: list[AgentMessage] = []

    def msg(from_agent: str, message_type: str, content: str, to_agent: str | None = None, evidence_refs: list[str] | None = None) -> dict:
        m = AgentMessage(from_agent=from_agent, to_agent=to_agent, message_type=message_type, content=content, evidence_refs=evidence_refs or [])
        agent_messages.append(m)
        return _event("agent_message", m.model_dump())

    try:
        # ---- Stage 1: Ingest ----
        yield _event("stage_start", {"stage": "ingest"})
        t = time.perf_counter()
        packet = fetch_full_packet(applicant_id)
        safe_packet = mask_pii(packet)
        flat_evidence = build_flat_evidence(packet)
        irregularity = detect_deposit_irregularity(packet["income"].get("bank_statement_transactions", []))
        timing_ms["ingest"] = round((time.perf_counter() - t) * 1000, 2)
        yield _event("stage_complete", {"stage": "ingest", "items": 4, "timing_ms": timing_ms["ingest"]})

        policy = get_active_policy()
        segment_cfg = get_segment_config(policy, PRODUCT)

        # ---- Stage 2: Reason ----
        yield _event("stage_start", {"stage": "reason"})
        t = time.perf_counter()

        eligibility = scoring.eligibility_check(flat_evidence, segment_cfg)
        yield msg("eligibility", "assessment", f"{eligibility['result']} — score_band '{eligibility['score_band']}'", evidence_refs=["bureau.score_band"])

        hard_rules_triggered: list[dict] = []
        affordability: AffordabilityAssessment | None = None
        risk: RiskAssessment | None = None
        consensus: dict | None = None
        outcome: str | None = None
        reason_code: str | None = None

        if eligibility["result"] == "FAIL":
            outcome, reason_code = "DECLINE", "BELOW_MINIMUM_CREDIT_PROFILE"
        else:
            hard_rules_triggered = scoring.evaluate_hard_rules(flat_evidence, segment_cfg, segment_cfg["hard_rules"], PRODUCT)
            if hard_rules_triggered:
                rule = hard_rules_triggered[0]
                outcome, reason_code = rule["action"], rule["reason_code"]
                yield msg("orchestrator", "escalate", f"Hard rule {rule['id']} triggered: {rule['condition']}")
            else:
                # Parallel Affordability + Risk assessment
                try:
                    affordability, risk = await asyncio.wait_for(
                        asyncio.gather(
                            _run_affordability(safe_packet["income"], irregularity, segment_cfg["affordability"]["dti_decline_ceiling"]),
                            _run_risk(safe_packet["delinquency"], safe_packet["exposure"], irregularity, packet["income"].get("employment_type", "unknown"), packet["income"].get("income_verification_status", "unknown")),
                        ),
                        timeout=AGENT_TIMEOUT_S,
                    )
                except (TimeoutError, asyncio.TimeoutError, RuntimeError) as agent_exc:
                    degradations.append(f"agent_unavailable ({agent_exc}): fell back to deterministic rules-only anchors")
                    dti = scoring.compute_dti(flat_evidence["monthly_income"], flat_evidence["monthly_obligations"], segment_cfg["affordability"]["dti_decline_ceiling"])
                    risk_anchor = scoring.compute_risk_anchor(flat_evidence["max_dpd"], flat_evidence["utilization_ratio"])
                    affordability = AffordabilityAssessment(assessment=dti["band"], score=dti["suggested_score"], confidence=0.5, factors=[], flags=["agent_fallback"], reasoning="Deterministic fallback: LLM assessment unavailable.")
                    risk = RiskAssessment(assessment=risk_anchor["band"], score=risk_anchor["suggested_score"], confidence=0.5, factors=[], flags=["agent_fallback"], reasoning="Deterministic fallback: LLM assessment unavailable.")

                yield msg("affordability", "assessment", f"{affordability.assessment} (score {affordability.score:.2f}, confidence {affordability.confidence:.2f}): {affordability.reasoning}", evidence_refs=[f.evidence_ref for f in affordability.factors])
                yield msg("risk", "assessment", f"{risk.assessment} (score {risk.score:.2f}, confidence {risk.confidence:.2f}): {risk.reasoning}", evidence_refs=[f.evidence_ref for f in risk.factors])

                # Collaboration round: Risk challenges Affordability
                if risk.concern_for_affordability:
                    yield msg("risk", "flag_concern", risk.concern_for_affordability, to_agent="affordability")
                    try:
                        affordability = await asyncio.wait_for(
                            _run_affordability(safe_packet["income"], irregularity, segment_cfg["affordability"]["dti_decline_ceiling"], concern=risk.concern_for_affordability),
                            timeout=AGENT_TIMEOUT_S,
                        )
                        yield msg("affordability", "provide_context", f"Reassessed: {affordability.assessment} (confidence {affordability.confidence:.2f}): {affordability.reasoning}", to_agent="risk")
                    except (TimeoutError, asyncio.TimeoutError, RuntimeError):
                        degradations.append("collaboration_unavailable: proceeded with pre-collaboration assessment")

                consensus = scoring.check_consensus(affordability.score, risk.score, affordability.confidence, risk.confidence, segment_cfg["consensus"])
                if not consensus["agree"]:
                    outcome, reason_code = "REFER", "CONFLICTING_SIGNALS"
                    yield msg("orchestrator", "escalate", f"Consensus check failed — score_gap={consensus['score_gap']:.2f}, min_confidence={consensus['min_confidence']:.2f}")

        timing_ms["reason"] = round((time.perf_counter() - t) * 1000, 2)
        yield _event("stage_complete", {"stage": "reason", "timing_ms": timing_ms["reason"]})

        # ---- Stage 3: Score ----
        yield _event("stage_start", {"stage": "score"})
        t = time.perf_counter()
        component_scores: dict[str, float] | None = None
        final_score: float | None = None
        decisive_factors: list[str] = []

        if outcome is None:
            component_scores = {"eligibility": 1.0, "affordability": affordability.score, "risk": risk.score}
            final_score = scoring.compute_weighted_score(1.0, affordability.score, risk.score, segment_cfg["scoring"]["weights"])
            outcome = scoring.apply_thresholds(final_score, segment_cfg["scoring"]["thresholds"])
            reason_code = {"APPROVE": "SCORE_ABOVE_THRESHOLD", "DECLINE": "SCORE_BELOW_THRESHOLD", "REFER": "SCORE_IN_REFER_BAND"}[outcome]
            decisive_factors = [f"affordability: {affordability.assessment} ({affordability.score:.2f})", f"risk: {risk.assessment} ({risk.score:.2f})"]
        elif reason_code == "BELOW_MINIMUM_CREDIT_PROFILE":
            decisive_factors = eligibility["reasons"]
        elif hard_rules_triggered:
            rule = hard_rules_triggered[0]
            decisive_factors = [f"hard rule {rule['id']}: {rule['condition']}"]
        elif reason_code == "CONFLICTING_SIGNALS":
            decisive_factors = [
                f"affordability: {affordability.assessment} (confidence {affordability.confidence:.2f})",
                f"risk: {risk.assessment} (confidence {risk.confidence:.2f})",
            ]

        timing_ms["score"] = round((time.perf_counter() - t) * 1000, 2)
        yield _event("stage_complete", {"stage": "score", "outcome": outcome, "timing_ms": timing_ms["score"]})

        # ---- Stage 4: Explain ----
        yield _event("stage_start", {"stage": "explain"})
        t = time.perf_counter()

        lineage = DecisionLineage(
            applicant_id=applicant_id,
            product=PRODUCT,
            policy_version=policy["version"],
            policy_hash=policy["_hash"],
            eligibility_result=eligibility,
            hard_rules_triggered=hard_rules_triggered,
            affordability_assessment=affordability.model_dump() if affordability else None,
            risk_assessment=risk.model_dump() if risk else None,
            consensus=consensus,
            component_scores=component_scores,
            final_score=final_score,
            thresholds=segment_cfg["scoring"]["thresholds"],
            decisive_factors=decisive_factors,
            agent_messages=agent_messages,
            evidence_snapshot=flat_evidence,
            degradations=degradations,
        )

        explanation: dict[str, str] | None = None
        try:
            result = await asyncio.wait_for(
                get_explanation_model().ainvoke(
                    [
                        {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Decision lineage:\n{lineage.model_dump_json(indent=2)}"},
                    ]
                ),
                timeout=EXPLAIN_TIMEOUT_S,
            )
            explanation = {"customer": result.customer, "reviewer": result.reviewer}
        except (TimeoutError, asyncio.TimeoutError, RuntimeError) as explain_exc:
            degradations.append(f"explanation_unavailable ({explain_exc}): fell back to template")

        if explanation is None:
            template_fields = {
                **flat_evidence,
                "dti_decline_ceiling": segment_cfg["affordability"]["dti_decline_ceiling"],
                "approve_threshold": segment_cfg["scoring"]["thresholds"]["approve"],
                "decline_threshold": segment_cfg["scoring"]["thresholds"]["decline"],
                "final_score": final_score or 0.0,
                "eligibility_score": (component_scores or {}).get("eligibility", 0.0),
                "affordability_score": (component_scores or {}).get("affordability", 0.0),
                "risk_score": (component_scores or {}).get("risk", 0.0),
                **(consensus or {}),
            }
            explanation = generate_template_explanation(reason_code, template_fields)

        timing_ms["explain"] = round((time.perf_counter() - t) * 1000, 2)
        lineage.timing_ms = timing_ms
        lineage.degradations = degradations
        yield _event("stage_complete", {"stage": "explain", "timing_ms": timing_ms["explain"]})

        # ---- Save + finish ----
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
        save_decision(record)

        yield _event("decision_made", record.model_dump())
        yield _event("done", {})

    except Exception as exc:  # noqa: BLE001 — surfaced to the client as a terminal SSE error, never a silent auto-approve
        yield _event("error", {"message": str(exc), "recoverable": False})
        yield _event("done", {})
