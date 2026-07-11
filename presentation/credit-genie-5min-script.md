# Credit Genie — 5-minute hackathon presentation

## Story spine

Banks have data, but cannot turn fragmented borrower evidence and changing credit policy into fast, consistent, explainable decisions across Personal Loans and BNPL.

Credit Genie solves this with one shared evidence and policy architecture, two execution modes, deterministic orchestration, and bounded agent collaboration.

Đức, Hoàng, and Dũng provide the human story. They are narrative characters, not replacements for the documented test fixtures. Sarah, Raj, Maria, James, and Aisha prove distinct outcomes and control behavior in the demo.

## Slide plan

| Time | Slide | Visual | Purpose |
|---|---|---|---|
| 0:00–0:25 | 1. The credit decision gap | `01-hero-credit-genie.png` | State problem and promise |
| 0:25–0:55 | 2. Why current workflow breaks | `02-borrower-case.png`, `03-underwriting-review.png`, `04-bnpl-decline.png` | Show fragmentation, policy friction, explanation gap |
| 0:55–1:25 | 3. Our approach: one architecture, two modes | Presenter-built split diagram | Explain Personal Loan vs BNPL execution |
| 1:25–2:10 | 4. High-level architecture | `05-credit-genie-architecture.png` with editable labels | Explain ingest, preparation, routing, scoring, output |
| 2:10–2:45 | 5. What “agentic” means here | `06-multi-agent-case.png` with editable labels | Explain roles, A2A challenge, determinism |
| 2:45–3:45 | 6. One-minute product demo | Screen recording | Prove decisions, explanations, speed, policy change |
| 3:45–4:35 | 7. Test coverage and controls | Persona/outcome table + policy editor screenshot | Prove distinct outcomes and runtime controls |
| 4:35–5:00 | 8. Close | `07-outcomes-close.png` | Re-state value |

## Full spoken script

### 1. The credit decision gap — 0:00–0:25

“Meet Đức, Hoàng, and Dũng.

Đức has just started a business and needs a Personal Loan. Hoàng is the person responsible for making a safe, consistent decision. Dũng is trying to use BNPL and receives a decline he cannot understand.

Banks do not lack credit data. The problem is that the evidence is fragmented, policies keep changing, and the final decision is often just an opaque score.

Credit Genie is an explainable credit decision engine built to solve that trade-off across Personal Loans and BNPL.”

### 2. Why the current workflow breaks — 0:25–0:55

“For Đức, recent hardship can hide new business potential. For Hoàng, the evidence is spread across bureau history, transactions, policy, and application data. For Dũng, the customer sees only a decline — not the evidence, reason, or next step.

A single application can combine bureau history, income, bank transactions, existing exposure, application data, policy rules, and historical outcomes.

These sources arrive in different shapes. Analysts or separate services repeatedly fetch, interpret, and reconcile them. Policy updates often require a deployment.

The result is slower investigation, inconsistent decisions, missed context, and less trust for customers, reviewers, and auditors.”

### 3. Our approach: one architecture, two execution modes — 0:55–1:25

“Credit Genie uses one shared policy schema and evidence format, but chooses execution depth by product.

Personal Loans use the full path: bounded agent reasoning, collaboration, deterministic scoring, and cited explanation — within a 60-second budget.

BNPL uses the fast path: deterministic rules only, zero LLM calls, and template-based explanation — under 2 seconds.

Same policy. Same evidence lineage. Different depth where the product needs it.”

### 4. High-level architecture — 1:25–2:10

“The request enters with an applicant and a product.

First, the evidence collector fetches the mock bureau, income and transaction data, exposure, policy, and historic outcomes. The preparation layer masks sensitive fields, normalizes the evidence, builds a flat packet, and detects useful signals such as irregular deposits.

The mode router sends Personal Loans to the full path and BNPL to the fast path.

For Personal Loans, the eligibility gate applies deterministic minimum criteria first. Affordability and Risk then assess their scoped evidence. The orchestrator combines their outputs, applies hard rules, weights, thresholds, and consensus checks, then generates explanations from the same decision lineage.

For BNPL, the rules engine evaluates eligibility, affordability, risk, exposure, and stacking directly. No LLM is on that path.

Every result returns a decision, evidence references, timing, confidence, and audience-specific explanation. The Personal Loan path streams stages and agent messages to the UI, so reasoning is visible instead of hidden.”

### 5. What “agentic” means here — 2:10–2:45

“Agentic does not mean letting one model decide everything.

Credit Genie has three decisioning roles. Eligibility is a rules-only gate. Affordability reasons about DTI, income stability, and bank-statement patterns. Risk checks delinquency, exposure, BNPL stacking, and fraud signals.

Risk can challenge Affordability. Affordability responds with a re-evaluation. If disagreement remains, the system escalates to REFER.

Python remains the deterministic orchestrator. It controls sequencing, timeouts, scoring, weights, thresholds, and consensus. Agents handle the narrow reasoning tasks where judgment adds value.

That separation gives us intelligence with reproducibility.”

### 6. One-minute product demo — 2:45–3:45

Use the real applicant picker and policy editor. Keep UI transitions fast. Voiceover:

**0:00–0:06 — Applicant picker**

“Here are five test personas. Each one is designed to prove a different decision path.”

**0:06–0:18 — Raj Patel, Personal Loan**

“We start with Raj Patel. His declared income conflicts with irregular deposits, so this is a case where agents must disagree productively.”

**0:18–0:31 — Full-path pipeline**

“The system ingests evidence, passes the eligibility gate, then runs Affordability and Risk with scoped context. Risk flags the deposit pattern and challenges the affordability assessment.”

**0:31–0:39 — REFER result**

“The disagreement is preserved in the lineage and produces REFER, with cited evidence instead of an unexplained score.”

**0:39–0:47 — Maria Santos, BNPL**

“Now Maria uses BNPL. This path detects exposure across five providers with deterministic rules, no LLM call, and a decision under the two-second constraint.”

**0:47–0:58 — Aisha Mohammed, policy change**

“Finally, Aisha is declined under policy v2.1 because her DTI is 45 percent and the ceiling is 40. We change the active YAML policy to a 50 percent ceiling, rerun without redeployment, and the result flips to APPROVE.”

**0:58–1:00 — Outcome table**

“Five personas, five intentional outcomes, one auditable engine.”

### 7. Test coverage and controls — 3:45–4:35

“The test set covers more than a happy path:

- Sarah Chen: APPROVE across Personal Loan and BNPL.
- Raj Patel: REFER from agent disagreement.
- Maria Santos: BNPL DECLINE from over-exposure.
- James Wilson: Personal Loan DECLINE from the 120-day delinquency hard rule.
- Aisha Mohammed: DECLINE to APPROVE after a runtime policy change.

The controls are explicit. Evidence is scoped per agent. Sensitive fields are masked. Rules and policy checks remain deterministic. Personal Loan agents run inside bounded timeouts: 25 seconds for reasoning and 30 seconds for explanation, within the 60-second product budget. BNPL avoids LLM latency completely and stays under 2 seconds.

Policy is versioned as YAML, decisions keep immutable lineage, and the UI streams the Personal Loan pipeline so reviewers can inspect what happened.”

### 8. Close — 4:35–5:00

“Credit Genie turns scattered evidence into a structured decision path.

It gives Personal Loans enough reasoning depth without losing control. It gives BNPL the speed of deterministic rules. It makes policy changes visible, agent collaboration inspectable, and explanations traceable to evidence.

Credit is not only a score. It is a decision built from evidence, policy, and judgment.

Credit Genie makes that decision faster, more consistent, and easier to explain.”

## Editable architecture labels

Add these labels over `05-credit-genie-architecture.png`:

1. **Sources** — Bureau · Income/transactions · Exposure · Application · Policy · Historic outcomes
2. **Evidence ingest + preparation** — Fetch · mask PII · normalize · flat evidence · signal detection · provenance
3. **Mode router** — Personal Loan full path / BNPL fast path
4. **Personal Loan** — Eligibility gate → Affordability + Risk → A2A challenge → deterministic scoring → explanation
5. **BNPL** — Rules-only evaluation → template explanation
6. **Output** — Decision · confidence · reason codes · evidence refs · timing · immutable lineage

## Editable multi-agent labels

Add these labels over `06-multi-agent-case.png`:

- **Eligibility** — rules-only minimum criteria and hard gate
- **Affordability** — DTI, income stability, transaction patterns
- **Risk** — delinquency, exposure, stacking, fraud signals; challenger role
- **Orchestrator** — deterministic sequencing, consensus, weights, thresholds, escalation
- **Explanation generator** — cited customer, reviewer, and audit views from one lineage source

## Demo safety checklist

- Preload all five personas; avoid login and network setup.
- Show Raj first because it proves real collaboration and REFER escalation.
- Show Maria second because it proves BNPL speed and zero LLM calls.
- Show Aisha last because policy-as-YAML becomes visually undeniable.
- Keep one evidence citation visible on each result.
- Show actual measured timing from the UI; do not invent p95 numbers.
- End with the five-outcome table and the policy version change.

## Visual direction

- Use cinematic 3D fintech visuals as atmosphere, not as source of truth.
- Use real UI screenshots for personas, outcomes, timings, agent messages, and policy changes.
- Keep labels and claims outside raster art so text stays readable and editable.
- Palette: midnight indigo, electric cyan, warm amber, coral exceptions.
