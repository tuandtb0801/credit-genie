# Credit Genie — Hackathon Scope

## Event
Agentic AI Build Week 2026 (GoTyme — Use Case 7)

## Build Window
2-3 days

## Demo Audience
Executive sponsors (visual impact, speed narrative, before/after)

## One-Line Problem
Bank cannot turn fragmented borrower evidence + changing credit policy into fast, consistent, explainable decisions across personal loans and BNPL.

## Scoped Problems (3 of 6)

| # | Problem | What We Build |
|---|---------|---------------|
| 1 | Fragmented evidence | Multi-source ingest with quality/freshness metadata |
| 2 | Slow policy change | Policy-as-YAML, no-deploy updates, simulation |
| 4 | Explanation gap | Cited rationale per audience (customer/reviewer/audit) |

## Deferred (Out of Scope)

- BNPL latency optimization beyond rules-only fast path (#3 infra depth)
- Full human review workflow (#5 — REFER exists as outcome, no reviewer UI)
- Scale/concurrency/idempotency (#6 — production concern)
- Real bureau/bank integrations
- Database/persistence (in-memory for hackathon)
- Auth, multi-tenancy, CI/CD
- Fairness/bias analysis
- Training a credit model from mock data

## Products
Both Personal Loan and BNPL (thin slice each)

| Product | Decision Speed | Method |
|---------|---------------|--------|
| Personal Loan | < 60s | Full agent reasoning (LLM) |
| BNPL | < 2s | Rules-only fast path (no LLM) |

## Core Components

1. **Data Ingest** — collect + normalize evidence from mock sources, flag missing
2. **Multi-Agent Reasoning** — 3 agents (Eligibility, Affordability, Risk) with visible collaboration
3. **Scoring Engine** — weighted aggregation + policy hard rules + thresholds
4. **Explanation Output** — 3 audience views from single lineage source
5. **Real-Time Pipeline Viz** — SSE-streamed stages + agent conversation in UI
6. **Policy Editor** — edit YAML in UI, simulate impact, re-run

## What "Agentic" Means Here

- Agents communicate (challenge, flag, escalate)
- Agent disagreement triggers REFER automatically
- Agents cite evidence — no hallucinated reasons
- Agents adapt to policy changes at runtime (no redeploy)
- All reasoning visible in real-time (not black box)

## Mock Data (Provided by GoTyme)

| Category | Fields |
|----------|--------|
| Bureau-style | credit_score, existing_exposures, delinquency_history |
| Income/affordability | monthly_income, employer, bank_statement_transactions |
| Policy/scorecard | rule_id, condition, segment, effective_date |
| Historic outcomes | applicant_id, decision, outcome (default/no_default) |

## Test Personas (5)

| Persona | Product | Expected | Demo Purpose |
|---------|---------|----------|--------------|
| Sarah Chen | PL + BNPL | APPROVE | Happy path |
| Raj Patel | PL | REFER | Contradictory income, agents disagree |
| Maria Santos | BNPL | DECLINE | Over-exposed |
| James Wilson | PL | DECLINE | Severe delinquency |
| Aisha Mohammed | PL | DECLINE→APPROVE | Policy change demo |

## Success Criteria

- [ ] Personal loan decision < 60s with cited reasoning
- [ ] BNPL decision < 2s (rules-based)
- [ ] Agent collaboration visible in UI (messages streamed)
- [ ] Change policy YAML → re-run → different outcome
- [ ] Simulation: "N of 5 past decisions would flip under new policy"
- [ ] 5 personas produce distinct, correct, explainable outcomes
- [ ] Exec understands story in 3-5 minute demo


## NOT Building

- Production-ready system
- Real integrations
- Model training
- Fairness proofs
- Load testing
- Multi-user/multi-tenant
