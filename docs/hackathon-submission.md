# Credit Genie — Hackathon Submission

## Elevator Pitch

Credit Genie uses collaborative AI agents to turn fragmented borrower evidence and evolving credit policy into fast, consistent, explainable lending decisions — delivering personal loan verdicts in under 60 seconds and BNPL approvals in under 2 seconds, with full audit trails and real-time reasoning visibility.

---

## Inspiration

Traditional credit decisioning at digital banks like GoTyme suffers from three core pain points: evidence is scattered across bureaus, bank statements, and internal systems with no unified view; policy changes require code deployments and weeks of development cycles; and decisions come out as opaque scores with no meaningful explanation for customers, reviewers, or auditors. We asked: what if AI agents could collaborate like a credit committee — each with a distinct role, challenging each other's findings, citing evidence, and adapting to policy changes in real-time without redeployment?

## What it does

Credit Genie is an agentic credit decision engine that supports two products through one architecture:

- **Personal Loans (Full Path)**: Three specialized AI agents — Eligibility, Affordability, and Risk — collaborate within a 60-second budget. The Risk agent adversarially challenges the Affordability agent's findings. When agents disagree, decisions automatically escalate to REFER status. Every conclusion cites specific evidence.
- **BNPL (Fast Path)**: Pure deterministic rules engine with zero LLM calls, delivering decisions in under 2 seconds with template-based explanations.

A live dashboard streams agent reasoning in real-time via SSE, showing the pipeline stages, agent conversations, and final decision with cited rationale. Credit policy lives as YAML files that can be updated without deployment — changes take effect on the next decision.

## How we built it

**Backend**: Python 3.12 with FastAPI, using Deep Agents framework + LangGraph for agent orchestration. LangChain-OpenAI powers the reasoning agents (Affordability, Risk, Explanation). The orchestrator itself is deterministic Python — scoring, weighting, and threshold comparison are math, not LLM judgment — ensuring reproducibility while agents handle nuanced reasoning.

**Frontend**: React 19 + TypeScript + Vite + Tailwind CSS 4. Real-time pipeline visualization consumes SSE streams showing each stage as it completes. Components include agent conversation viewer, decision cards with outcome badges, applicant picker with 5 test personas, and a policy editor.

**Architecture decisions**:
- Deterministic orchestration with LLM reasoning at leaf nodes only
- Agent-to-Agent protocol where Risk challenges Affordability and Affordability responds
- Policy-as-YAML with no-deploy updates and simulation capability
- Evidence packets scoped per agent to prevent information overload
- Full decision lineage tracking (timing, evidence used, agent outputs, confidence scores)

## Challenges we ran into

- **Balancing determinism with intelligence**: The scoring layer must be reproducible for audit, but reasoning about income stability or fraud signals needs LLM judgment. Solution: Python orchestrates deterministically, agents reason within bounded stages.
- **Agent disagreement handling**: Making the Risk agent's adversarial challenges productive rather than blocking. Had to carefully design the A2A protocol so challenges improve accuracy without creating infinite loops.
- **60-second time budget**: Running multiple LLM agents sequentially within a hard budget required parallel execution where possible and strict per-agent timeouts (25s reasoning, 30s explanation).
- **BNPL latency constraint**: 2-second budget means zero tolerance for LLM calls. Built an entirely separate deterministic path sharing the same policy schema and evidence format.

## Accomplishments that we're proud of

- Full working system in 2-3 days with real agent collaboration, not just prompt chaining
- Agent disagreement automatically produces REFER decisions (demonstrated with Raj Patel persona — contradictory income triggers debate between Affordability and Risk agents)
- Policy changes work at runtime — Aisha Mohammed's persona demonstrates DECLINE flipping to APPROVE after a policy threshold update, no restart needed
- Real-time streaming visibility into agent reasoning — decisions aren't black boxes
- Clean separation: deterministic math where auditability demands it, LLM reasoning only where human-like judgment adds value

## What we learned

- Agentic doesn't mean "let the LLM decide everything." The most reliable architecture uses agents for reasoning and plain code for coordination.
- Agent collaboration needs explicit protocols. Without structured challenge/response patterns, agents produce vague or repetitive outputs.
- Policy-as-code (YAML) with runtime reloading is surprisingly powerful for financial products where rules change weekly.
- SSE streaming transforms the UX of AI-powered decisions — watching agents think builds trust in a way that a loading spinner never can.

## What's next for Credit Genie

- Human-in-the-loop reviewer UI for REFER decisions
- Fairness/bias analysis layer across protected attributes
- Real bureau and bank integrations (replacing mock data)
- Multi-tenancy and persistent storage for production deployment
- BNPL latency optimization with caching and pre-computation
- Training feedback loops where reviewer overrides improve agent prompts

## Built with

- Python
- FastAPI
- Deep Agents
- LangGraph
- LangChain + OpenAI
- React
- TypeScript
- Vite
- Tailwind CSS
- SSE (Server-Sent Events)
- Pydantic
- YAML (Policy Engine)
- AWS

## OpenAI (via LangChain-OpenAI)

LangChain-OpenAI (`langchain-openai>=1.3.5`) powers the LLM reasoning within agents:

- **Affordability Agent** — uses OpenAI to reason about income stability, DTI analysis, and deposit pattern irregularities
- **Risk Agent** — uses OpenAI to assess delinquency severity, detect fraud signals, and generate adversarial challenges to the Affordability agent
- **Explanation Generator** — uses OpenAI to produce cited, audience-appropriate rationale (customer-facing vs. auditor-facing explanations)

The orchestrator itself is deterministic Python — OpenAI is used only at leaf-node reasoning stages where human-like judgment adds value, keeping scoring and threshold logic reproducible for audit.

## Deployment

Deployed on AWS:

- Backend containerized and deployed on AWS infrastructure
- LLM access via OpenAI API
- Frontend served as static assets via S3 + CloudFront
