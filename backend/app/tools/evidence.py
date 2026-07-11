"""Evidence fetch, PII masking, and derived-signal helpers.

Evidence fixtures carry no PII fields (no name/address/national ID) by design —
masking here mainly strips free-text employer/label strings before they reach
the LLM, keeping the "LLM never sees PII" pattern demonstrable even on mock data.
"""

import json
import re
from typing import Any

from app.config import EVIDENCE_ROOT

_SOURCES = ("bureau", "income", "exposure", "delinquency")

_EMPLOYER_RE = re.compile(r"employer|studio|logistics|consulting|systems|group", re.IGNORECASE)


def fetch_evidence_source(applicant_id: str, source: str) -> dict[str, Any]:
    """Read one raw evidence source (bureau/income/exposure/delinquency) for an applicant."""
    if source not in _SOURCES:
        raise ValueError(f"Unknown evidence source: {source}")
    path = EVIDENCE_ROOT / applicant_id / f"{source}.json"
    if not path.exists():
        return {"applicant_id": applicant_id, "confidence": "missing", "freshness_days": None}
    return json.loads(path.read_text())


def fetch_full_packet(applicant_id: str) -> dict[str, dict[str, Any]]:
    """Fetch all four evidence sources for an applicant, in parallel-shaped form."""
    return {source: fetch_evidence_source(applicant_id, source) for source in _SOURCES}


def mask_pii(packet: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return an LLM-safe copy of the packet with employer name and transaction labels redacted."""
    safe = json.loads(json.dumps(packet))
    income = safe.get("income", {})
    if "employer" in income:
        income["employer"] = "[redacted]"
    for tx in income.get("bank_statement_transactions", []):
        tx["label"] = _EMPLOYER_RE.sub("[employer]", tx.get("label", ""))
    return safe


def build_flat_evidence(packet: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Flatten the packet into the scalar fields hard rules and eligibility checks operate on."""
    bureau = packet.get("bureau", {})
    income = packet.get("income", {})
    exposure = packet.get("exposure", {})
    delinquency = packet.get("delinquency", {})

    monthly_income = income.get("monthly_income", 0) or 0
    monthly_obligations = income.get("monthly_obligations", 0) or 0
    dti_ratio = (monthly_obligations / monthly_income) if monthly_income else 1.0

    return {
        "credit_score": bureau.get("credit_score"),
        "score_band": bureau.get("score_band"),
        "credit_history_months": bureau.get("credit_history_months"),
        "monthly_income": monthly_income,
        "monthly_obligations": monthly_obligations,
        "dti_ratio": round(dti_ratio, 4),
        "bnpl_active_count": exposure.get("bnpl_active_count", 0),
        "utilization_ratio": exposure.get("utilization_ratio", 0),
        "total_exposure": exposure.get("total_exposure", 0),
        "max_dpd": delinquency.get("max_dpd", 0),
    }


def detect_deposit_irregularity(bank_tx: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically flag whether recent deposits look like regular payroll or irregular transfers."""
    if not bank_tx:
        return {"pattern": "unknown", "note": "No transaction history available."}

    amounts = [tx.get("amount", 0) for tx in bank_tx]
    labels = [tx.get("label", "").lower() for tx in bank_tx]

    avg = sum(amounts) / len(amounts)
    variance_pct = (max(amounts) - min(amounts)) / avg if avg else 0
    looks_like_payroll = all("payroll" in label for label in labels)

    if looks_like_payroll and variance_pct < 0.05:
        return {"pattern": "regular", "note": "Deposits are evenly sized, recurring payroll credits."}
    return {
        "pattern": "irregular",
        "note": f"Deposit amounts vary by {variance_pct:.0%} and are not labeled as payroll.",
    }
