"""Core decision + ledger endpoints."""

import json
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.bnpl import decide_bnpl
from app.config import APPLICANTS_PATH, EVIDENCE_ROOT
from app.ledger import get_decision, list_decisions
from app.orchestrator import decide_personal_loan
from app.tools.evidence import build_flat_evidence, detect_deposit_irregularity, fetch_full_packet

router = APIRouter(prefix="/api")


class DecideRequest(BaseModel):
    applicant_id: str
    product: str


@router.get("/applicants")
def get_applicants() -> list[dict]:
    """List the demo applicant personas."""
    return json.loads(APPLICANTS_PATH.read_text())


@router.get("/applicants/{applicant_id}/evidence")
def get_applicant_evidence(applicant_id: str) -> dict:
    """The decisive evidence signals for an applicant — what the rules and agents actually cite."""
    if not (EVIDENCE_ROOT / applicant_id).is_dir():
        raise HTTPException(status_code=404, detail=f"Applicant '{applicant_id}' not found.")
    packet = fetch_full_packet(applicant_id)
    income = packet["income"]
    return {
        "applicant_id": applicant_id,
        "signals": build_flat_evidence(packet),
        "income_verification_status": income.get("income_verification_status", "unknown"),
        "employment_type": income.get("employment_type", "unknown"),
        "deposit_pattern": detect_deposit_irregularity(income.get("bank_statement_transactions", [])),
        "bnpl_providers": packet["exposure"].get("bnpl_providers", []),
        "sources": {
            source: {"confidence": data.get("confidence"), "freshness_days": data.get("freshness_days")}
            for source, data in packet.items()
        },
    }


@router.post("/decide")
async def decide(request: DecideRequest):
    """Run a decision. BNPL returns a plain JSON response; personal_loan streams SSE."""
    if request.product == "bnpl":
        start = time.perf_counter()
        record = decide_bnpl(request.applicant_id)
        return {**record.model_dump(), "latency_ms": round((time.perf_counter() - start) * 1000, 2)}

    if request.product == "personal_loan":
        async def stream():
            async for event in decide_personal_loan(request.applicant_id):
                yield {"event": event["event"], "data": json.dumps(event["data"], default=str)}

        return EventSourceResponse(stream())

    raise HTTPException(status_code=400, detail=f"Unknown product '{request.product}'. Expected 'personal_loan' or 'bnpl'.")


@router.get("/decisions")
def get_decisions(applicant_id: str | None = None) -> list[dict]:
    """List saved decisions, optionally filtered by applicant."""
    return [d.model_dump() for d in list_decisions(applicant_id)]


@router.get("/decisions/{decision_id}")
def get_decision_by_id(decision_id: str) -> dict:
    """Fetch one decision record by id."""
    record = get_decision(decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Decision '{decision_id}' not found.")
    return record.model_dump()
