"""Shared Pydantic schemas: agent structured output, decision lineage, ledger records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Outcome = Literal["APPROVE", "DECLINE", "REFER"]
Product = Literal["personal_loan", "bnpl"]


class Factor(BaseModel):
    """A single cited piece of evidence that fed into an assessment."""

    name: str
    value: str
    evidence_ref: str = Field(description="Which evidence source this came from, e.g. 'income.bank_statement_transactions'")
    impact: Literal["positive", "negative", "neutral"]


class AffordabilityAssessment(BaseModel):
    """Structured output required from the Affordability agent."""

    assessment: Literal["adequate", "marginal", "inadequate", "uncertain"]
    score: float = Field(ge=0, le=1, description="Normalized affordability score, 0=cannot service debt, 1=fully affordable")
    confidence: float = Field(ge=0, le=1)
    factors: list[Factor]
    flags: list[str] = Field(default_factory=list)
    reasoning: str
    concern_for_risk: str | None = Field(
        default=None, description="Set only if something here should make the Risk agent reconsider its assessment"
    )


class RiskAssessment(BaseModel):
    """Structured output required from the Risk agent."""

    assessment: Literal["low", "moderate", "elevated", "high"]
    score: float = Field(ge=0, le=1, description="Normalized risk score, 0=high risk, 1=low risk (higher is better, matches other components)")
    confidence: float = Field(ge=0, le=1)
    factors: list[Factor]
    flags: list[str] = Field(default_factory=list)
    reasoning: str
    concern_for_affordability: str | None = Field(
        default=None, description="Set only if something here should make the Affordability agent reconsider its assessment"
    )


class ExplanationViews(BaseModel):
    """Structured output required from the Explanation agent (LLM path only)."""

    customer: str = Field(description="Plain-language, empathetic, actionable. No internal scores or agent names.")
    reviewer: str = Field(description="Factual, detailed, references the decisive factors and agent assessments.")


class AgentMessage(BaseModel):
    """One entry in the visible agent conversation stream."""

    from_agent: str
    to_agent: str | None = None
    message_type: Literal["assessment", "flag_concern", "request_review", "provide_context", "escalate"]
    content: str
    evidence_refs: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DecisionLineage(BaseModel):
    """Everything needed to replay and audit a decision."""

    applicant_id: str
    product: Product
    policy_version: str
    policy_hash: str
    eligibility_result: dict[str, Any]
    hard_rules_triggered: list[dict[str, Any]] = Field(default_factory=list)
    affordability_assessment: dict[str, Any] | None = None
    risk_assessment: dict[str, Any] | None = None
    consensus: dict[str, Any] | None = None
    component_scores: dict[str, float] | None = None
    final_score: float | None = None
    thresholds: dict[str, float] | None = None
    decisive_factors: list[str] = Field(default_factory=list)
    agent_messages: list[AgentMessage] = Field(default_factory=list)
    evidence_snapshot: dict[str, Any] = Field(default_factory=dict)
    timing_ms: dict[str, float] = Field(default_factory=dict)
    degradations: list[str] = Field(default_factory=list)


class DecisionRecord(BaseModel):
    """Immutable record written to the audit ledger."""

    decision_id: str
    applicant_id: str
    product: Product
    outcome: Outcome
    reason_code: str
    lineage: DecisionLineage
    explanation: dict[str, str]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latency_ms: float | None = None
