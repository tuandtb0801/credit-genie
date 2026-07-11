"""Policy engine: load/validate active policy, draft lifecycle, simulation, activate, rollback."""

import hashlib
import shutil
from datetime import date, datetime, timezone
from typing import Any

import yaml

from app.config import POLICY_ACTIVE_PATH, POLICY_DRAFTS_ROOT, POLICY_HISTORY_ROOT
from app.tools import scoring
from app.tools.evidence import build_flat_evidence, fetch_full_packet

REQUIRED_SEGMENT_KEYS = {"mode", "time_budget_ms", "scoring", "features", "eligibility", "affordability", "risk"}


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def load_policy_file(path) -> dict[str, Any]:
    raw_text = path.read_text()
    policy = yaml.safe_load(raw_text)
    policy["_hash"] = _hash_text(raw_text)
    policy["_path"] = str(path)
    return policy


def get_active_policy() -> dict[str, Any]:
    """Load the currently active policy, tagged with its content hash for lineage locking."""
    return load_policy_file(POLICY_ACTIVE_PATH)


def get_segment_config(policy: dict[str, Any], product: str) -> dict[str, Any]:
    """Extract the segment config for a product: weights, thresholds, hard rules, features."""
    segment = policy["segments"][product]
    return {
        **segment,
        "hard_rules": policy["hard_rules"],
        "consensus": policy["consensus"],
        "policy_version": policy["version"],
        "policy_hash": policy["_hash"],
    }


def list_drafts() -> list[dict[str, Any]]:
    """List draft policies awaiting simulation/approval."""
    drafts = []
    for path in sorted(POLICY_DRAFTS_ROOT.glob("*.yaml")):
        policy = load_policy_file(path)
        drafts.append(
            {
                "filename": path.name,
                "version": policy.get("version"),
                "status": policy.get("status"),
                "change_reason": policy.get("change_reason"),
                "drafted_by": policy.get("drafted_by"),
            }
        )
    return drafts


def validate_policy(policy: dict[str, Any]) -> list[str]:
    """Schema + sanity checks. Returns a list of errors; empty means valid."""
    errors = []
    for product, segment in policy.get("segments", {}).items():
        missing = REQUIRED_SEGMENT_KEYS - segment.keys()
        if missing:
            errors.append(f"segment '{product}' missing keys: {sorted(missing)}")
            continue
        weights = segment["scoring"]["weights"]
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"segment '{product}' weights sum to {weight_sum}, expected 1.0")
        thresholds = segment["scoring"]["thresholds"]
        if thresholds["decline"] >= thresholds["approve"]:
            errors.append(f"segment '{product}' decline threshold must be below approve threshold")

    if not policy.get("hard_rules"):
        errors.append("policy has no hard_rules defined")

    return errors


def _recompute_decision(flat_evidence: dict[str, Any], segment_cfg: dict[str, Any], product: str, fallback_scores: dict[str, float] | None) -> dict[str, Any]:
    """Deterministically recompute an outcome under a candidate policy for simulation."""
    eligibility = scoring.eligibility_check(flat_evidence, segment_cfg)
    if eligibility["result"] == "FAIL":
        return {"outcome": "DECLINE", "reason_code": "ELIGIBILITY_FAIL"}

    hard_hits = scoring.evaluate_hard_rules(flat_evidence, segment_cfg, segment_cfg["hard_rules"], product)
    if hard_hits:
        rule = hard_hits[0]
        return {"outcome": rule["action"], "reason_code": rule["reason_code"]}

    if fallback_scores and "affordability_score" in fallback_scores and "risk_score" in fallback_scores:
        affordability_score = fallback_scores["affordability_score"]
        risk_score = fallback_scores["risk_score"]
    else:
        dti = scoring.compute_dti(
            flat_evidence["monthly_income"], flat_evidence["monthly_obligations"], segment_cfg["affordability"]["dti_decline_ceiling"]
        )
        risk_anchor = scoring.compute_risk_anchor(flat_evidence["max_dpd"], flat_evidence["utilization_ratio"])
        affordability_score = dti["suggested_score"]
        risk_score = risk_anchor["suggested_score"]

    final_score = scoring.compute_weighted_score(1.0, affordability_score, risk_score, segment_cfg["scoring"]["weights"])
    outcome = scoring.apply_thresholds(final_score, segment_cfg["scoring"]["thresholds"])
    reason_code = "SCORE_BELOW_THRESHOLD" if outcome == "DECLINE" else ("SCORE_IN_REFER_BAND" if outcome == "REFER" else "SCORE_ABOVE_THRESHOLD")
    return {"outcome": outcome, "reason_code": reason_code, "final_score": final_score}


def simulate_policy_change(draft_filename: str, applicant_ids: list[str], product: str, decision_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Re-run scoring for a set of applicants under the active policy vs a draft.

    `decision_lookup` maps applicant_id -> that applicant's most recent decision lineage
    dict (if any), used to reuse real agent scores instead of re-invoking the LLM.
    """
    active_policy = get_active_policy()
    draft_policy = load_policy_file(POLICY_DRAFTS_ROOT / draft_filename)

    results = []
    changed_count = 0
    for applicant_id in applicant_ids:
        packet = fetch_full_packet(applicant_id)
        flat_evidence = build_flat_evidence(packet)

        prior = decision_lookup.get(applicant_id)
        fallback_scores = None
        if prior and prior.get("component_scores"):
            fallback_scores = {
                "affordability_score": prior["component_scores"].get("affordability"),
                "risk_score": prior["component_scores"].get("risk"),
            }

        old_segment = get_segment_config(active_policy, product)
        new_segment = get_segment_config(draft_policy, product)

        old = _recompute_decision(flat_evidence, old_segment, product, fallback_scores)
        new = _recompute_decision(flat_evidence, new_segment, product, fallback_scores)

        changed = old["outcome"] != new["outcome"]
        changed_count += changed
        results.append({"applicant_id": applicant_id, "old": old, "new": new, "changed": changed})

    return {
        "draft_version": draft_policy["version"],
        "active_version": active_policy["version"],
        "total": len(results),
        "changed": changed_count,
        "results": results,
    }


def activate_policy(draft_filename: str, approved_by: str) -> dict[str, Any]:
    """Approve and activate a draft: archive the current active policy, promote the draft."""
    POLICY_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    active_policy = get_active_policy()

    archive_name = f"credit_policy_v{active_policy['version']}.yaml"
    shutil.copy(POLICY_ACTIVE_PATH, POLICY_HISTORY_ROOT / archive_name)

    draft_path = POLICY_DRAFTS_ROOT / draft_filename
    draft = yaml.safe_load(draft_path.read_text())
    draft["status"] = "active"
    draft["effective_date"] = date.today().isoformat()
    draft["approved_by"] = approved_by
    draft["activated_at"] = datetime.now(timezone.utc).isoformat()

    POLICY_ACTIVE_PATH.write_text(yaml.safe_dump(draft, sort_keys=False))
    draft_path.unlink()

    return load_policy_file(POLICY_ACTIVE_PATH)


def rollback_policy() -> dict[str, Any]:
    """Revert to the most recently archived policy version."""
    history_files = sorted(POLICY_HISTORY_ROOT.glob("*.yaml"), key=lambda p: p.stat().st_mtime)
    if not history_files:
        raise ValueError("No previous policy version to roll back to.")

    previous_path = history_files[-1]
    current = get_active_policy()

    demoted_name = f"credit_policy_v{current['version']}.yaml"
    shutil.move(str(POLICY_ACTIVE_PATH), str(POLICY_HISTORY_ROOT / demoted_name))
    shutil.move(str(previous_path), str(POLICY_ACTIVE_PATH))

    return load_policy_file(POLICY_ACTIVE_PATH)
