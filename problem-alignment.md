# Agentic Credit Decision Engine — Team Problem Alignment

## Problem statement

> **Bank cannot reliably turn fragmented, time-sensitive borrower evidence and changing credit policy into fast, consistent, explainable, and auditable decisions across personal loans and BNPL.**

We are not primarily solving “how to make an AI approve loans.” We are solving **credit-decision operations**: how evidence, policy, automation, human judgment, and governance work together under strict time limits.

```text
Fragmented evidence + rigid policy + different product speeds
           + uncertain cases + explanation obligations
                              ↓
       Slow, inconsistent, opaque, hard-to-change decisions
                              ↓
False declines | over-lending | manual cost | checkout loss | audit risk
```

## Core problems

| Problem | What breaks today | Why it matters |
|---|---|---|
| **1. Fragmented and uncertain evidence** | Bureau, exposure, delinquency, income, expenses, and documents come from different sources. Data may be missing, stale, unverified, or contradictory. BNPL obligations across providers may be invisible; thin-file applicants lack traditional history. | Bad evidence creates false approvals, false declines, inconsistent affordability checks, and manual investigation. Missing must never be treated as zero. |
| **2. Slow and risky policy change** | Credit rules live in scorecards, rule trees, spreadsheets, and code. Risk-team intent passes through engineering releases. Impact, conflicts, effective dates, approvers, and rollback may be unclear. | Bank cannot react quickly without increasing operational or compliance risk. “No code deployment” must still retain testing and approval. |
| **3. Two incompatible decision speeds** | Personal loans need richer document and affordability review; sponsor wants 80% under 60 seconds. BNPL must finish during checkout in under two seconds, including reasoning. | One generic workflow either misses BNPL latency or oversimplifies personal-loan risk. Timeout and dependency behavior must be explicit. |
| **4. Explanations may not match real decision** | Systems may return only score or generic rejection. Free-form AI can produce plausible rationale that did not cause outcome. | Applicant cannot understand or correct data; bank cannot defend decision. Every reason must trace to actual evidence, calculation, rule, and policy version. |
| **5. Uncertainty and human review are inconsistent** | Missing data, conflicting income, near-threshold affordability, thin files, and provider failures do not fit clean approve/decline choices. Manual overrides may be unstructured or rubber-stamped. | `REFER` must be first-class outcome with clear evidence packet, meaningful reviewer authority, and logged override reason. |
| **6. Automation scales risk as well as speed** | Historical outcomes may contain old policy or bias. Alternative data may improve inclusion but introduce proxy/privacy risk. Concurrent BNPL checkouts and duplicate requests can exceed exposure limits. Tiny mock datasets encourage overclaiming. | Fast system needs deterministic behavior, safe failure handling, idempotency, exposure consistency, monitoring, and claims limited to available evidence. |

## Stakeholders

- **Applicant:** fast outcome, understandable reason, correction/review path.
- **Risk team:** change policy quickly, understand impact, retain approval authority.
- **Underwriter/operations:** less evidence chasing, clearer referred cases.
- **Engineering/product:** fewer policy-specific releases, stable decision contracts.
- **Compliance/audit:** exact replay, faithful reasons, accountable human actions.
- **Business:** balance conversion with affordability, loss, fraud, and operating cost.

## Scope boundary

### In scope

- Application-time evidence and data quality.
- Eligibility, affordability, exposure, delinquency, and referral policy.
- `APPROVE`, `DECLINE`, and `REFER` decisions.
- Personal-loan and BNPL decision-time flows.
- Policy draft, test, compare, approve, activate, and rollback lifecycle.
- Plain-language reasons grounded in actual decision factors.
- Decision lineage, human review, override, latency, timeout, and idempotency.

### Out of scope

- Pricing, disbursement, servicing, collections, or recovery.
- Full KYC, AML, or fraud platform; consume mock signal only.
- Training a credit model from five applicants.
- Live bureau/bank integrations.
- Proving fairness, default reduction, or production compliance from mock data.

## Success conditions

1. **Speed:** personal-loan target met; BNPL p95/p99 below two seconds end-to-end.
2. **Consistency:** same evidence and versions produce same decision and reasons.
3. **Evidence safety:** missing, stale, unverified, and contradictory data handled explicitly.
4. **Explanation fidelity:** every decline reason maps to actual decisive factor and evidence.
5. **Lineage:** every decision replayable with inputs, calculations, policy, timing, and human actions.
6. **Policy agility:** change without application release, but with testing, approval, versioning, and rollback.
7. **Human control:** uncertain cases receive meaningful review; every override records actor and reason.
8. **Honest validation:** five mock cases prove workflow, traceability, and latency—not model quality or fairness.

## Team decisions still needed

1. Exact jurisdiction and BNPL product definition.
2. Whether `REFER` is acceptable at checkout and resulting customer experience.
3. Critical versus optional evidence, plus freshness limits.
4. Availability of cross-provider BNPL exposure data.
5. Policy approver and individual-override authority.
6. Required reason-code taxonomy.
7. Whether LLM must run inside BNPL request path.
8. Load and percentile used to validate two-second target.

## Meeting talk track

> We are solving credit-decision operations, not replacing underwriters with an LLM. Bank must combine fragmented borrower evidence with changing policy, then deliver consistent and explainable outcomes across document-rich personal loans and sub-two-second BNPL. Current process is slow to change, weak at handling uncertainty, and hard to replay or defend. Success means fast decisions, exact lineage, safe referral, governed policy change without application releases, and meaningful human control.
