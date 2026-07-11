"""Template-based explanation generation: BNPL's only path, and the PL fallback when
the LLM explanation fails validation or times out. Filled entirely from decision lineage
— never invents a reason that isn't already in the lineage.
"""

from typing import Any

_CUSTOMER_TEMPLATES = {
    "SEVERE_DELINQUENCY": "We're not able to approve this application. Our records show a significant history of missed payments, which means we can't extend new credit right now.",
    "UNAFFORDABLE": "We're not able to approve this application. Based on your income and current monthly obligations, this loan amount would leave too little room in your budget.",
    "THIN_FILE": "We need a bit more information before we can decide. Your credit history is still short, so this application has been passed to a reviewer.",
    "OVER_EXPOSED": "We're not able to approve this purchase right now. You currently have several active buy-now-pay-later plans, and this would push your total obligations above what we can respons­ibly extend.",
    "BELOW_MINIMUM_CREDIT_PROFILE": "We're not able to approve this application based on your current credit profile.",
    "CONFLICTING_SIGNALS": "We need a closer look before we can decide. Some of the information on this application doesn't line up cleanly, so a reviewer will take a look and follow up with you.",
    "SCORE_ABOVE_THRESHOLD": "Good news — your application has been approved.",
    "SCORE_BELOW_THRESHOLD": "We're not able to approve this application based on an overall review of your credit profile, income, and current obligations.",
    "SCORE_IN_REFER_BAND": "Your application is close to our approval line, so we're having a reviewer take a closer look. We'll follow up shortly.",
}

_REVIEWER_TEMPLATES = {
    "SEVERE_DELINQUENCY": "Hard rule HR-001 triggered: max_dpd={max_dpd} >= 90. Decision made without weighted scoring.",
    "UNAFFORDABLE": "Hard rule HR-002 triggered: dti_ratio={dti_ratio:.0%} exceeds the active dti_decline_ceiling ({dti_decline_ceiling:.0%}) for this segment.",
    "THIN_FILE": "Hard rule HR-003 triggered: credit_history_months={credit_history_months} is below the segment minimum.",
    "OVER_EXPOSED": "Hard rule HR-004 triggered: bnpl_active_count={bnpl_active_count} / utilization_ratio={utilization_ratio:.0%} exceeds policy caps.",
    "BELOW_MINIMUM_CREDIT_PROFILE": "Eligibility gate FAIL: score_band '{score_band}' is below the segment's minimum.",
    "CONFLICTING_SIGNALS": "Consensus check failed after the collaboration round — score_gap={score_gap:.2f} / min_confidence={min_confidence:.2f} against policy thresholds. Both agent viewpoints are attached below.",
    "SCORE_ABOVE_THRESHOLD": "final_score={final_score:.2f} met or exceeded the approve threshold ({approve_threshold:.2f}). Component scores: eligibility={eligibility_score:.2f}, affordability={affordability_score:.2f}, risk={risk_score:.2f}.",
    "SCORE_BELOW_THRESHOLD": "final_score={final_score:.2f} was at or below the decline threshold ({decline_threshold:.2f}). Component scores: eligibility={eligibility_score:.2f}, affordability={affordability_score:.2f}, risk={risk_score:.2f}.",
    "SCORE_IN_REFER_BAND": "final_score={final_score:.2f} fell between the decline ({decline_threshold:.2f}) and approve ({approve_threshold:.2f}) thresholds.",
}


def generate_template_explanation(reason_code: str, template_fields: dict[str, Any]) -> dict[str, str]:
    """Fill the customer/reviewer templates for a reason code from lineage-derived fields.

    Missing format fields degrade to the raw customer message with no reviewer detail,
    rather than raising — a template gap should never block a decision from completing.
    """
    customer = _CUSTOMER_TEMPLATES.get(reason_code, "Your application has been processed. Contact support for details.")
    reviewer_template = _REVIEWER_TEMPLATES.get(reason_code)
    try:
        reviewer = reviewer_template.format(**template_fields) if reviewer_template else customer
    except (KeyError, ValueError):
        reviewer = f"[template fill failed for {reason_code}] " + customer
    return {"customer": customer, "reviewer": reviewer}
