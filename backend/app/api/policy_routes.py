"""Policy lifecycle endpoints: view, list drafts, validate, simulate, activate, rollback."""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import APPLICANTS_PATH, POLICY_DRAFTS_ROOT
from app.ledger import decision_lookup_by_applicant
from app.tools import policy as policy_tools
from app.tools.backtest import backtest_policy_change

router = APIRouter(prefix="/api/policy")


def _clean(policy: dict) -> dict:
    return {"hash": policy.get("_hash"), **{k: v for k, v in policy.items() if not k.startswith("_")}}


@router.get("/active")
def get_active() -> dict:
    return _clean(policy_tools.get_active_policy())


@router.get("/drafts")
def get_drafts() -> list[dict]:
    return policy_tools.list_drafts()


class ValidateRequest(BaseModel):
    filename: str


@router.post("/validate")
def validate(request: ValidateRequest) -> dict:
    path = POLICY_DRAFTS_ROOT / request.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Draft '{request.filename}' not found.")
    policy = policy_tools.load_policy_file(path)
    errors = policy_tools.validate_policy(policy)
    return {"valid": not errors, "errors": errors}


class SimulateRequest(BaseModel):
    filename: str
    product: str
    applicant_ids: list[str] | None = None


@router.post("/simulate")
def simulate(request: SimulateRequest) -> dict:
    applicant_ids = request.applicant_ids
    if applicant_ids is None:
        all_applicants = json.loads(APPLICANTS_PATH.read_text())
        applicant_ids = [a["applicant_id"] for a in all_applicants if request.product in a["products"]]

    return policy_tools.simulate_policy_change(request.filename, applicant_ids, request.product, decision_lookup_by_applicant())


class DraftRuleRequest(BaseModel):
    intent: str
    requested_by: str


@router.post("/draft-rule")
def draft_rule(request: DraftRuleRequest) -> dict:
    """Agent-draft a hard rule from plain English. Produces a governed draft — never touches the active policy."""
    if not request.intent.strip():
        raise HTTPException(status_code=400, detail="Intent must not be empty.")
    from app.agents.rule_drafter import draft_rule_from_intent

    try:
        return draft_rule_from_intent(request.intent.strip(), request.requested_by)
    except RuntimeError as exc:  # missing API key — agent unavailable, drafting stays manual
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class BacktestRequest(BaseModel):
    filename: str
    product: str


@router.post("/backtest")
def backtest(request: BacktestRequest) -> dict:
    """Replay the synthetic historic book under active vs draft policy — the risk cost of the change."""
    path = POLICY_DRAFTS_ROOT / request.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Draft '{request.filename}' not found.")
    try:
        return backtest_policy_change(request.filename, request.product)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ActivateRequest(BaseModel):
    filename: str
    approved_by: str


@router.post("/activate")
def activate(request: ActivateRequest) -> dict:
    errors = policy_tools.validate_policy(policy_tools.load_policy_file(POLICY_DRAFTS_ROOT / request.filename))
    if errors:
        raise HTTPException(status_code=400, detail={"message": "Draft failed validation.", "errors": errors})
    try:
        return _clean(policy_tools.activate_policy(request.filename, request.approved_by))
    except ValueError as exc:  # stale draft — forked from an older active policy
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/rollback")
def rollback() -> dict:
    try:
        return _clean(policy_tools.rollback_policy())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
