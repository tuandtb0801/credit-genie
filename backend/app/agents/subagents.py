"""LLM-backed reasoning agents for the Personal Loan full path: Affordability and Risk
(deep agents with structured output), plus the Explanation agent.

Eligibility is deliberately not here — per docs/agent-design.md it never uses LLM
reasoning, so it's plain Python in app/tools/scoring.eligibility_check.

Pipeline sequencing, the consensus check, and final scoring stay in app/orchestrator.py
as deterministic Python — see that module's docstring for why.
"""

from functools import lru_cache

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config import OPENAI_MODEL, WORKSPACE_ROOT, require_api_key
from app.models import AffordabilityAssessment, ExplanationViews, RiskAssessment
from app.tools import scoring
from app.agents.prompts import AFFORDABILITY_SYSTEM_PROMPT, EXPLANATION_SYSTEM_PROMPT, RISK_SYSTEM_PROMPT


@tool
def compute_dti(monthly_income: float, monthly_obligations: float, dti_decline_ceiling: float) -> dict:
    """Compute debt-to-income ratio and a deterministic affordability anchor score/band."""
    return scoring.compute_dti(monthly_income, monthly_obligations, dti_decline_ceiling)


@tool
def compute_risk_anchor(max_dpd: int, utilization_ratio: float) -> dict:
    """Compute a deterministic delinquency/exposure risk anchor score/band."""
    return scoring.compute_risk_anchor(max_dpd, utilization_ratio)


def _model() -> ChatOpenAI:
    require_api_key()
    return ChatOpenAI(model=OPENAI_MODEL, temperature=0)


def _backend() -> FilesystemBackend:
    return FilesystemBackend(root_dir=str(WORKSPACE_ROOT))


@lru_cache(maxsize=1)
def get_affordability_agent():
    return create_deep_agent(
        model=_model(),
        tools=[compute_dti],
        system_prompt=AFFORDABILITY_SYSTEM_PROMPT,
        response_format=AffordabilityAssessment,
        backend=_backend(),
        name="affordability-agent",
    )


@lru_cache(maxsize=1)
def get_risk_agent():
    return create_deep_agent(
        model=_model(),
        tools=[compute_risk_anchor],
        system_prompt=RISK_SYSTEM_PROMPT,
        response_format=RiskAssessment,
        backend=_backend(),
        name="risk-agent",
    )


@lru_cache(maxsize=1)
def get_explanation_model():
    """A direct structured-output call, not a deep agent: no tools, no delegation, no
    filesystem — the full agent scaffolding only added latency for what's a single-shot
    text transform of the decision lineage.
    """
    return _model().with_structured_output(ExplanationViews)
