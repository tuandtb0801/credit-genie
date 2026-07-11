# Credit Genie

> **Agentic AI Build Week 2026 — GoTyme Use Case 7**

AI-powered credit decision engine where collaborative agents turn fragmented borrower evidence and evolving policy into fast, consistent, explainable lending decisions.

## Problem

Banks cannot turn fragmented borrower evidence + changing credit policy into fast, consistent, explainable decisions across personal loans and BNPL.

| # | Problem | Impact |
|---|---------|--------|
| 1 | Fragmented evidence | Data scattered across bureaus, statements, internal systems — no unified view |
| 2 | Slow policy change | Rule updates require code deployments and weeks of dev cycles |
| 3 | Explanation gap | Opaque scores with no meaningful rationale for customers, reviewers, or auditors |

## Approach

**Key insight**: Use agents for reasoning, plain code for coordination.

- **Deterministic orchestration** — Python controls the pipeline (scoring, weighting, thresholds). Reproducible for audit.
- **LLM reasoning at leaf nodes** — Agents handle nuanced judgment (income stability, fraud signals, explanation generation).
- **Agent collaboration via A2A protocol** — Risk agent adversarially challenges Affordability agent. Disagreement triggers automatic REFER.
- **Policy-as-YAML** — Credit rules updated at runtime without redeployment.
- **Dual execution modes** — Same policy schema, different speed/depth tradeoffs per product.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Dashboard (SSE)                        │
│  Pipeline Viz │ Agent Conversations │ Decision Card │ Policy Ed  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │    FastAPI Backend     │
                    │    Mode Selector       │
                    └───┬───────────────┬───┘
                        │               │
           ┌────────────▼──┐    ┌───────▼────────────┐
           │   FAST PATH   │    │     FULL PATH      │
           │   (BNPL)      │    │   (Personal Loan)  │
           │               │    │                    │
           │  Budget: 2s   │    │  Budget: 60s       │
           │  No LLM       │    │  LLM reasoning     │
           │  Rules only   │    │  Agent collab      │
           └───────────────┘    └────────┬───────────┘
                                         │
                         ┌───────────────┼───────────────┐
                         │               │               │
                    ┌────▼────┐    ┌─────▼─────┐   ┌────▼────┐
                    │Eligibility│   │Affordability│  │  Risk   │
                    │  Agent   │    │   Agent    │   │  Agent  │
                    │          │    │            │   │         │
                    │ Gate     │    │ DTI, income│   │ Adverse │
                    │ check    │    │ stability  │   │ review  │
                    └──────────┘    └─────▲──────┘   └────┬────┘
                                          │               │
                                          └── challenge ──┘
```

### Agent Roles

| Agent | Role | Method |
|-------|------|--------|
| **Orchestrator** | Coordinate pipeline, enforce budgets, save decisions | Deterministic Python |
| **Eligibility** | Gate check — minimum criteria (score band, blacklist) | Rules only, no LLM |
| **Affordability** | Can applicant service this debt? (DTI, income patterns) | LLM reasoning |
| **Risk** | What could go wrong? Adversarially challenges Affordability | LLM reasoning |

### Decision Outcomes

- **APPROVE** — All agents agree, score above threshold
- **DECLINE** — Hard rule failure or score below threshold
- **REFER** — Agent disagreement or low confidence, needs human review

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Agent Framework | Deep Agents, LangGraph, LangChain-OpenAI |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4 |
| Streaming | SSE (Server-Sent Events) |
| Policy Engine | YAML with runtime reload |
| Validation | Pydantic |

## Project Structure

```
credit-genie/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── app/
│   │   ├── orchestrator.py     # Personal Loan full path
│   │   ├── bnpl.py             # BNPL fast path (no LLM)
│   │   ├── agents/             # LangGraph agent definitions
│   │   ├── tools/              # Scoring, policy, evidence, explanation
│   │   ├── api/                # REST + SSE routes
│   │   ├── models.py           # Pydantic schemas
│   │   └── ledger.py           # Decision record storage
│   └── policy/                 # YAML policy files
├── frontend/
│   ├── src/
│   │   ├── pages/              # Dashboard, PolicyEditor
│   │   ├── components/         # PipelineViz, AgentConversation, DecisionCard
│   │   └── api/                # SSE client
│   └── package.json
└── docs/                       # Architecture, scope, agent design
```

## Test Personas

| Persona | Product | Expected | Demonstrates |
|---------|---------|----------|--------------|
| Sarah Chen | PL + BNPL | APPROVE | Happy path |
| Raj Patel | PL | REFER | Agent disagreement (contradictory income) |
| Maria Santos | BNPL | DECLINE | Over-exposed |
| James Wilson | PL | DECLINE | Severe delinquency |
| Aisha Mohammed | PL | DECLINE→APPROVE | Runtime policy change |

## Quick Start

```bash
# Backend
cd backend
uv sync
cp .env.example .env  # Add OPENAI_API_KEY
uv run uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Documentation

- [Architecture](docs/architecture.md)
- [Agent Design & A2A Protocol](docs/agent-design.md)
- [Decision Modes & Controls](docs/decision-modes-and-controls.md)
- [Hackathon Submission](docs/hackathon-submission.md)
- [Scope](docs/scope.md)
