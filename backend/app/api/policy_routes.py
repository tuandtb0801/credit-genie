"""Policy lifecycle endpoints: view, list drafts, validate, simulate, activate, rollback."""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import APPLICANTS_PATH, POLICY_DRAFTS_ROOT
from app.ledger import decision_lookup_by_applicant
from app.tools import policy as policy_tools

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


class ActivateRequest(BaseModel):
    filename: str
    approved_by: str


@router.post("/activate")
def activate(request: ActivateRequest) -> dict:
    errors = policy_tools.validate_policy(policy_tools.load_policy_file(POLICY_DRAFTS_ROOT / request.filename))
    if errors:
        raise HTTPException(status_code=400, detail={"message": "Draft failed validation.", "errors": errors})
    return _clean(policy_tools.activate_policy(request.filename, request.approved_by))


@router.post("/rollback")
def rollback() -> dict:
    try:
        return _clean(policy_tools.rollback_policy())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
