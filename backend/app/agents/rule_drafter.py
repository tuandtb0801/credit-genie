"""Agentic rule drafting: plain-English analyst intent -> a governed hard-rule draft.

Safety model: the LLM never authors a condition string. It emits structured clauses
(whitelisted field, whitelisted operator, bounded value); the condition is assembled and
validated deterministically here, then dry-run through the same restricted evaluator the
decision path uses. The output is a *draft* policy file — it still has to pass the human
simulate/back-test/approve/activate gates before it can affect a single decision.
"""

import re
from typing import Any, Literal

import yaml
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import OPENAI_MODEL, POLICY_ACTIVE_PATH, POLICY_DRAFTS_ROOT, require_api_key
from app.tools.policy import get_active_policy, list_drafts, load_policy_file, validate_policy
from app.tools.scoring import _safe_eval_condition

# The only evidence fields a generated rule may reference (all numeric, from flat evidence).
FIELD_CATALOG: dict[str, str] = {
    "credit_score": "bureau credit score (500-850)",
    "credit_history_months": "length of credit history in months",
    "monthly_income": "verified/declared monthly income in dollars",
    "monthly_obligations": "existing monthly debt obligations in dollars",
    "dti_ratio": "debt-to-income ratio, 0.0-1.0",
    "bnpl_active_count": "number of currently active BNPL plans",
    "utilization_ratio": "credit utilization ratio, 0.0-1.0",
    "total_exposure": "total outstanding exposure in dollars",
    "max_dpd": "worst delinquency in days past due",
}

# Policy-config references a clause may compare against instead of a literal number.
CONFIG_REFS = (
    "affordability.dti_decline_ceiling",
    "eligibility.min_credit_history_months",
    "risk.max_bnpl_stacking",
    "risk.max_utilization",
)

_RATIO_FIELDS = {"dti_ratio", "utilization_ratio"}
_REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,39}$")

FieldName = Literal[
    "credit_score",
    "credit_history_months",
    "monthly_income",
    "monthly_obligations",
    "dti_ratio",
    "bnpl_active_count",
    "utilization_ratio",
    "total_exposure",
    "max_dpd",
]


class RuleClause(BaseModel):
    """One comparison in the rule condition."""

    field: FieldName
    operator: Literal[">", ">=", "<", "<=", "=="]
    value: float | str = Field(description=f"A number, or one of the policy references: {', '.join(CONFIG_REFS)}")


class DraftedRule(BaseModel):
    """The structured rule proposal."""

    clauses: list[RuleClause] = Field(min_length=1, max_length=3)
    joiner: Literal["and", "or"] = "and"
    action: Literal["DECLINE", "REFER"]
    reason_code: str = Field(description="SCREAMING_SNAKE_CASE code, e.g. EXCESSIVE_EXPOSURE")
    description: str = Field(description="One plain-language sentence a regulator could read.")
    applies_to: list[Literal["personal_loan", "bnpl"]] = Field(min_length=1)


class DraftRuleDecision(BaseModel):
    """Structured output required from the rule-drafting agent: a rule, or a refusal."""

    refused: bool = Field(description="True when the intent cannot be faithfully AND lawfully expressed with the available fields.")
    refusal_reason: str | None = Field(default=None, description="Plain-language reason shown to the analyst when refused.")
    rule: DraftedRule | None = Field(default=None, description="The drafted rule. Must be null when refused.")


RULE_DRAFTER_SYSTEM_PROMPT = f"""\
You translate a credit risk analyst's plain-English intent into ONE structured hard rule
for Credit Genie's underwriting policy.

Available evidence fields (the ONLY fields you may use):
{chr(10).join(f"- {name}: {meaning}" for name, meaning in FIELD_CATALOG.items())}

A clause value is either a literal number or one of these policy references:
{chr(10).join(f"- {ref}" for ref in CONFIG_REFS)}

Rules you must follow:
- Express the intent with 1-3 clauses joined by a single 'and'/'or'. Do not add conditions
  the analyst didn't ask for.
- action: REFER when the intent is review/escalation/manual look; DECLINE when the intent
  is to block/reject. Hard rules can never auto-approve.
- reason_code: short SCREAMING_SNAKE_CASE that names the risk (not the action).
- description: one plain sentence restating the rule for an auditor.
- applies_to: only the products the analyst mentioned; both if unspecified.
- REFUSE (refused=true, rule=null, give refusal_reason) when the intent cannot be
  faithfully expressed with the available fields. NEVER substitute a placeholder or
  "closest approximation" rule — a rule that doesn't mean what the analyst asked is worse
  than no rule.
- REFUSE any intent that targets a specific person or a protected/identity characteristic
  (name, gender, race, religion, nationality, address, employer) — underwriting rules may
  only use the credit-evidence fields above.
- REFUSE intents asking to auto-approve; hard rules can only DECLINE or REFER.
"""


def build_condition(rule: DraftedRule) -> str:
    """Assemble the condition string from validated clause parts — the LLM never writes it."""
    parts = [f"{c.field} {c.operator} {c.value}" for c in rule.clauses]
    return f" {rule.joiner} ".join(parts)


def validate_drafted_rule(rule: DraftedRule) -> list[str]:
    """Deterministic guardrails on the structured rule. Returns errors; empty means safe."""
    errors = []
    for clause in rule.clauses:
        if isinstance(clause.value, str):
            if clause.value not in CONFIG_REFS:
                errors.append(f"clause value '{clause.value}' is not an allowed policy reference")
        else:
            if not (clause.value == clause.value and abs(clause.value) != float("inf")):  # NaN/inf
                errors.append(f"clause value {clause.value} is not a finite number")
            elif clause.field in _RATIO_FIELDS and not 0 <= clause.value <= 1.5:
                errors.append(f"{clause.field} threshold {clause.value} outside sane range 0-1.5")
            elif clause.field not in _RATIO_FIELDS and not 0 <= clause.value <= 10_000_000:
                errors.append(f"{clause.field} threshold {clause.value} outside sane range")

    if not _REASON_CODE_RE.match(rule.reason_code):
        errors.append(f"reason_code '{rule.reason_code}' must be SCREAMING_SNAKE_CASE (3-40 chars)")

    if errors:
        return errors

    # Dry-run the assembled condition through the same restricted evaluator the engine uses.
    sample_evidence = {name: 1 for name in FIELD_CATALOG}
    policy = get_active_policy()
    segment = policy["segments"]["personal_loan"]
    try:
        _safe_eval_condition(build_condition(rule), sample_evidence, {**segment, "hard_rules": [], "consensus": {}})
    except Exception as exc:  # noqa: BLE001 — any evaluator failure means the rule is unsafe
        errors.append(f"assembled condition failed safe evaluation: {exc}")
    return errors


def _next_rule_id() -> str:
    ids = [r["id"] for r in get_active_policy().get("hard_rules", [])]
    for draft in list_drafts():
        draft_policy = load_policy_file(POLICY_DRAFTS_ROOT / draft["filename"])
        ids += [r["id"] for r in draft_policy.get("hard_rules", [])]
    max_num = max((int(m.group(1)) for i in ids if (m := re.match(r"HR-(\d+)", i))), default=0)
    return f"HR-{max_num + 1:03d}"


def _next_version() -> str:
    versions = [get_active_policy().get("version", "2.1")] + [d.get("version") or "0" for d in list_drafts()]
    major, minor = max((tuple(int(p) for p in str(v).split(".")[:2]) for v in versions))
    return f"{major}.{minor + 1}"


def rule_impact_on_book(condition: str, applies_to: list[str]) -> dict[str, float] | None:
    """Semantic sanity check: what share of the 1,000-loan historic book would this rule
    trigger on, per product? Catches structurally-valid but absurd rules (e.g. a condition
    that fires on everyone) before a human ever sees the Activate button."""
    from app.tools.backtest import load_history_book

    try:
        records = load_history_book()["records"]
    except FileNotFoundError:
        return None
    policy = get_active_policy()
    impact = {}
    for product in applies_to:
        segment = policy["segments"][product]
        hits = sum(bool(_safe_eval_condition(condition, r["features"], segment)) for r in records)
        impact[product] = round(hits / len(records), 4)
    return impact


def draft_rule_from_intent(intent: str, requested_by: str) -> dict[str, Any]:
    """LLM-draft a rule from plain English, guardrail it, and write a governed policy draft."""
    require_api_key()
    model = ChatOpenAI(model=OPENAI_MODEL, temperature=0).with_structured_output(DraftRuleDecision)
    decision: DraftRuleDecision = model.invoke(
        [
            {"role": "system", "content": RULE_DRAFTER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyst intent: {intent}"},
        ]
    )

    if decision.refused or decision.rule is None:
        return {
            "created": False,
            "refused": True,
            "refusal_reason": decision.refusal_reason or "The agent could not express this intent with the available underwriting fields.",
            "errors": [],
        }
    drafted = decision.rule

    errors = validate_drafted_rule(drafted)
    if errors:
        return {"created": False, "refused": False, "errors": errors, "drafted": drafted.model_dump()}

    condition = build_condition(drafted)
    rule = {
        "id": _next_rule_id(),
        "description": drafted.description,
        "condition": condition,
        "action": drafted.action,
        "reason_code": drafted.reason_code,
        "applies_to": list(drafted.applies_to),
    }

    impact = rule_impact_on_book(condition, rule["applies_to"])
    warnings = []
    if impact:
        worst = max(impact.values())
        if worst >= 0.5:
            warnings.append(
                f"This rule would trigger on {worst:.0%} of the 1,000-loan historic book — "
                "check that it means what you intended before approving."
            )

    # New draft = active policy + the new rule, with draft metadata. Never touches the active file.
    policy = yaml.safe_load(POLICY_ACTIVE_PATH.read_text())
    policy["version"] = _next_version()
    policy["status"] = "draft"
    policy["effective_date"] = None
    policy["approved_by"] = None
    policy["drafted_by"] = f"rule-agent on behalf of {requested_by}"
    policy["change_reason"] = f"Agent-drafted rule from analyst intent: \"{intent}\""
    policy["hard_rules"] = [*policy.get("hard_rules", []), rule]

    policy_errors = validate_policy(policy)
    if policy_errors:
        return {"created": False, "refused": False, "errors": policy_errors, "drafted": drafted.model_dump()}

    filename = f"credit_policy_v{policy['version']}_rule_draft.yaml"
    POLICY_DRAFTS_ROOT.mkdir(parents=True, exist_ok=True)
    (POLICY_DRAFTS_ROOT / filename).write_text(yaml.safe_dump(policy, sort_keys=False))

    return {
        "created": True,
        "refused": False,
        "filename": filename,
        "version": policy["version"],
        "rule": rule,
        "impact": impact,
        "warnings": warnings,
        "errors": [],
    }
