# Credit Genie — Decision Modes, Accuracy, Speed & Banking Controls

## 1. Two Products, One Architecture, Two Execution Modes

The core insight: **same policy, same evidence schema, different execution strategy.**

```
                         ┌─────────────────────────┐
                         │    APPLICATION REQUEST   │
                         │  { product, applicant }  │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │     MODE SELECTOR        │
                         │  product == "bnpl"       │
                         │    → FAST PATH           │
                         │  product == "personal_loan"│
                         │    → FULL PATH           │
                         └──────┬──────────┬───────┘
                                │          │
                    ┌───────────▼──┐  ┌────▼────────────┐
                    │  FAST PATH   │  │  FULL PATH      │
                    │  (BNPL)      │  │  (Personal Loan) │
                    │              │  │                  │
                    │  Budget: 2s  │  │  Budget: 60s    │
                    │  1 agent call│  │  LLM reasoning  │
                    │  No collab   │  │  Agent collab   │
                    │  Template    │  │  Rich explain   │
                    │  explain     │  │                  │
                    └──────────────┘  └─────────────────┘
```

### 1.1 Personal Loan — Full Path

```
┌──────────────────────────────────────────────────────────────────────┐
│  FULL PATH — PERSONAL LOAN (budget: 60s)                             │
│                                                                      │
│  Time allocation:                                                    │
│  ├── Evidence collection (parallel)          ~2-3s                   │
│  ├── Eligibility agent (rules)               ~50ms                   │
│  ├── Affordability agent (LLM)               ~8-15s                  │
│  ├── Risk agent (LLM + rules)                ~5-10s                  │
│  ├── Agent collaboration (if triggered)      ~3-8s                   │
│  ├── Scoring + policy rules                  ~50ms                   │
│  ├── Explanation generation (LLM)            ~3-5s                   │
│  └── Total typical                           ~15-30s                 │
│                                                                      │
│  Features enabled:                                                   │
│  ✓ Full LLM reasoning over bank statements                          │
│  ✓ Agent-to-agent challenge/collaboration                           │
│  ✓ Rich natural language explanation                                 │
│  ✓ Uncertainty detection → REFER                                     │
│  ✓ Multi-pass: agent can request additional evidence                 │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 BNPL — Fast Path

```
┌──────────────────────────────────────────────────────────────────────┐
│  FAST PATH — BNPL (budget: 2s, p95 target)                           │
│                                                                      │
│  Time allocation:                                                    │
│  ├── Evidence lookup (pre-cached/indexed)     ~50-100ms              │
│  ├── Eligibility rules                        ~10ms                  │
│  ├── Affordability + risk anchors              ~10ms                  │
│  ├── Single-pass structured reasoning agent   ≤1800ms                 │
│  ├── Scoring + threshold                      ~10ms                  │
│  ├── Template explanation                     ~10ms                  │
│  └── Total target                             <2000ms p95            │
│                                                                      │
│  Features enabled:                                                   │
│  ✓ One bounded reasoning-agent call                                 │
│  ✓ Deterministic final rules, score, and thresholds                 │
│  ✓ Pre-computed affordability (from last PL assessment or cached)    │
│  ✓ Template-based explanation (filled from rule that fired)          │
│  ✗ No agent collaboration                                           │
│  ✗ No multi-pass evidence gathering                                  │
│  ✓ Low-confidence/timeout agent responses safely trigger REFER       │
│                                                                      │
│  Tradeoff acknowledged:                                              │
│  Less reasoning depth. Compensated by:                               │
│  - Tighter thresholds (more conservative)                            │
│  - Lower loan amounts (bounded risk per decision)                    │
│  - Higher DECLINE rate acceptable for speed                          │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.3 How Same Policy Serves Both

```yaml
# policy/credit_policy_v2.1.yaml

segments:
  personal_loan:
    mode: "full"
    time_budget_ms: 60000
    scoring:
      weights: { eligibility: 0.25, affordability: 0.40, risk: 0.35 }
      thresholds: { approve: 0.70, decline: 0.35 }
    features:
      llm_reasoning: true
      agent_collaboration: true
      multi_pass_evidence: true
      
  bnpl:
    mode: "fast"
    time_budget_ms: 2000
    scoring:
      weights: { eligibility: 0.30, affordability: 0.35, risk: 0.35 }
      thresholds: { approve: 0.75, decline: 0.40 }  # tighter = more conservative
    features:
      llm_reasoning: true
      agent_collaboration: false
      multi_pass_evidence: false
      agent_mode: single_pass

# Same hard rules apply to BOTH:
hard_rules:
  - id: "HR-001"
    condition: "max_dpd >= 90"
    action: "DECLINE"
    applies_to: ["personal_loan", "bnpl"]
```

---

## 2. Accuracy Strategy

### 2.1 What "Accuracy" Means in Credit Decisions

Not ML accuracy (precision/recall). Credit accuracy = **correct application of policy to evidence, consistently, with no false reasoning.**

| Dimension | Definition | How We Ensure |
|-----------|-----------|---------------|
| **Correctness** | Decision matches what policy prescribes for this evidence | Deterministic rules for clear cases; LLM constrained by structured output |
| **Consistency** | Same evidence + same policy = same outcome always | Versioned policy + evidence snapshot + deterministic scoring |
| **Completeness** | All relevant evidence considered, nothing ignored | Evidence packet tracks what's present AND what's missing |
| **Faithfulness** | Explanation matches actual decision factors | Explanation generated FROM lineage, not alongside |
| **Conservatism** | When uncertain, fail safe (REFER not auto-approve) | Explicit uncertainty handling, agent disagreement → REFER |

### 2.2 Accuracy Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  ACCURACY CONTROLS                                                    │
│                                                                      │
│  Layer 1: EVIDENCE QUALITY                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Every evidence item carries:                                    │ │
│  │ • confidence: "verified" | "declared" | "inferred" | "missing" │ │
│  │ • freshness_days: how old is this data?                        │ │
│  │ • source: where did it come from?                              │ │
│  │                                                                │ │
│  │ Rules:                                                         │ │
│  │ • "missing" NEVER treated as zero or clean                     │ │
│  │ • "inferred" triggers lower confidence in scoring              │ │
│  │ • freshness > N days → stale flag → may trigger REFER         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Layer 2: AGENT CONSTRAINTS                                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ LLM agents use STRUCTURED OUTPUT (not free-form):              │ │
│  │                                                                │ │
│  │ • Must cite evidence_ref for every claim                       │ │
│  │ • Must output confidence score (0-1) for assessment            │ │
│  │ • Cannot invent facts not in evidence packet                   │ │
│  │ • Low confidence → flags uncertainty (not guesses)             │ │
│  │                                                                │ │
│  │ Schema enforcement:                                            │ │
│  │ {                                                              │ │
│  │   "assessment": "adequate | inadequate | uncertain",           │ │
│  │   "confidence": 0.0-1.0,                                      │ │
│  │   "factors": [{ "name": str, "value": any,                    │ │
│  │                  "evidence_ref": str, "impact": str }],        │ │
│  │   "flags": [str],                                             │ │
│  │   "reasoning": str                                            │ │
│  │ }                                                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Layer 3: SCORING DETERMINISM                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Agent outputs (structured) → deterministic math:               │ │
│  │                                                                │ │
│  │ • Weighted sum = fixed formula                                 │ │
│  │ • Threshold comparison = boolean                               │ │
│  │ • Hard rules = exact condition matching                        │ │
│  │ • No randomness in final decision                              │ │
│  │                                                                │ │
│  │ LLM variability confined to:                                   │ │
│  │ • HOW it interprets evidence (assessment)                      │ │
│  │ • WHAT it says in explanation (natural language)                │ │
│  │                                                                │ │
│  │ LLM variability NOT allowed in:                                │ │
│  │ • Final score calculation                                      │ │
│  │ • Threshold decision (approve/decline/refer)                   │ │
│  │ • Policy rule evaluation                                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Layer 4: VALIDATION & CALIBRATION                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ • Run same applicant N times → outcome should be identical     │ │
│  │   (if not, agent confidence too low → force REFER)             │ │
│  │ • Simulate policy against historic outcomes                    │ │
│  │ • Compare agent assessment vs known outcomes                   │ │
│  │ • Flag drift: if approval rate shifts > X% without policy      │ │
│  │   change, something is wrong                                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 Accuracy vs Speed Tradeoff Matrix

```
                    HIGH ACCURACY
                         │
                         │   Personal Loan
                         │   (full reasoning,
                         │    agent collaboration,
                         │    multi-pass)
                         │         ●
                         │
                         │
                         │              BNPL
                         │              (rules only,
                         │               conservative
                         │               thresholds)
                         │                  ●
                         │
─────────────────────────┼─────────────────────────── FAST
         SLOW            │
                         │
                    LOW ACCURACY

Both stay in upper half. BNPL compensates for less reasoning
with more conservative thresholds (higher bar to approve).
```

---

## 3. Speed Strategy

### 3.1 Latency Budget Breakdown

```
┌──────────────────────────────────────────────────────────────────────┐
│  LATENCY MANAGEMENT                                                   │
│                                                                      │
│  Principle: Every stage has a time budget. Exceed → degrade or skip. │
│                                                                      │
│  Personal Loan (60s total):                                          │
│  ┌──────────┬─────────┬──────────────────────────────────────────┐  │
│  │ Stage    │ Budget  │ On Timeout                                │  │
│  ├──────────┼─────────┼──────────────────────────────────────────┤  │
│  │ Ingest   │ 5s      │ Proceed with partial evidence + flags    │  │
│  │ Agents   │ 30s     │ Use whatever assessments completed       │  │
│  │ Scoring  │ 100ms   │ Should never timeout (deterministic)     │  │
│  │ Explain  │ 10s     │ Fall back to template explanation        │  │
│  │ Buffer   │ 15s     │ Safety margin                            │  │
│  └──────────┴─────────┴──────────────────────────────────────────┘  │
│                                                                      │
│  BNPL (2s total):                                                    │
│  ┌──────────┬─────────┬──────────────────────────────────────────┐  │
│  │ Stage    │ Budget  │ On Timeout                                │  │
│  ├──────────┼─────────┼──────────────────────────────────────────┤  │
│  │ Ingest   │ 500ms   │ Use cached data only. No fresh fetch.    │  │
│  │ Rules    │ 100ms   │ Should never timeout                     │  │
│  │ Scoring  │ 50ms    │ Should never timeout                     │  │
│  │ Explain  │ 50ms    │ Template only (pre-built)                │  │
│  │ Buffer   │ 1300ms  │ Safety margin                            │  │
│  └──────────┴─────────┴──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Speed Techniques

```
┌──────────────────────────────────────────────────────────────────────┐
│  SPEED OPTIMIZATIONS                                                  │
│                                                                      │
│  1. PARALLEL EXECUTION                                               │
│     Affordability + Risk agents run simultaneously (not sequential)   │
│     Evidence sources fetched in parallel (not waterfall)              │
│                                                                      │
│  2. EARLY TERMINATION                                                │
│     Eligibility FAIL → skip Affordability + Risk entirely            │
│     Hard rule triggered → skip scoring, go straight to decision      │
│                                                                      │
│  3. PRE-COMPUTATION (BNPL)                                           │
│     DTI pre-calculated from last full assessment                     │
│     Exposure totals indexed and cached                               │
│     Bureau score cached with TTL                                     │
│                                                                      │
│  4. STREAMING (Personal Loan)                                        │
│     Don't wait for full response — stream partial assessments        │
│     Frontend shows progress immediately                              │
│     Agent messages visible as they generate                          │
│                                                                      │
│  5. GRACEFUL DEGRADATION                                             │
│     LLM timeout → fall back to rules-only for that agent             │
│     Missing evidence → decide with what you have + flag              │
│     Agent collaboration timeout → proceed without collaboration      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 Timeout Cascade

```
              Normal Flow              Degraded Flow (timeout)
              
Evidence:     All 4 sources OK    →    2/4 sources returned
                                        Missing flagged, proceed

Agents:       All 3 assess        →    Affordability LLM timeout
                                        Fall back to DTI-only rules
                                        
Collaboration: Risk challenges    →    Collaboration timeout (8s)
               Affordability          Skip collaboration, use
               responds                individual assessments

Explanation:  LLM generates       →    LLM timeout
              rich narrative          Use template fill
                                      
Decision:     Always completes (deterministic scoring = <100ms)
```

---

## 4. Banking Controls (Security, Governance, Compliance)

### 4.1 Security Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  SECURITY LAYERS                                                      │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 1: DATA PROTECTION                                      │ │
│  │                                                                │ │
│  │  • PII never sent to LLM in raw form                           │ │
│  │    - Names → anonymized tokens (Applicant_001)                 │ │
│  │    - IDs → masked (XXX-XXX-1234)                               │ │
│  │    - Addresses → not included (not decision-relevant)          │ │
│  │                                                                │ │
│  │  • LLM receives ONLY decision-relevant fields:                 │ │
│  │    income, DTI, score band, exposure amounts, DPD counts       │ │
│  │                                                                │ │
│  │  • Evidence packet has "safe_for_llm" flag per field           │ │
│  │    Only flagged fields pass to agent prompts                   │ │
│  │                                                                │ │
│  │  • Full PII available in audit trail (encrypted at rest)       │ │
│  │    but NEVER in LLM context window                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 2: LLM CONTAINMENT                                     │ │
│  │                                                                │ │
│  │  • LLM cannot access external systems                          │ │
│  │  • LLM cannot modify policy or data                            │ │
│  │  • LLM output validated against schema before use              │ │
│  │  • LLM does NOT make final decision — scoring engine does      │ │
│  │  • Prompt injection defense:                                   │ │
│  │    - Evidence values treated as data (escaped in prompt)       │ │
│  │    - System prompt locked (not user-editable)                  │ │
│  │    - Output schema enforced (rejects free-form if malformed)   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 3: ACCESS CONTROL                                       │ │
│  │                                                                │ │
│  │  Roles:                                                        │ │
│  │  • viewer    — see decisions, explanations                     │ │
│  │  • operator  — submit applications, trigger decisions          │ │
│  │  • policy_editor — modify policy (draft only)                  │ │
│  │  • policy_approver — activate/rollback policy versions         │ │
│  │  • auditor   — full lineage access, replay capability          │ │
│  │  • admin     — system configuration                            │ │
│  │                                                                │ │
│  │  Separation of duties:                                         │ │
│  │  • Person who edits policy ≠ person who approves it            │ │
│  │  • Person who overrides decision must not be the applicant     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 4: API SECURITY                                         │ │
│  │                                                                │ │
│  │  • All endpoints authenticated (JWT/API key)                   │ │
│  │  • Rate limiting per client                                    │ │
│  │  • Input validation (Pydantic schemas, reject malformed)       │ │
│  │  • No sensitive data in error responses                        │ │
│  │  • TLS everywhere                                              │ │
│  │  • Request signing for decision submissions                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Governance Framework

```
┌──────────────────────────────────────────────────────────────────────┐
│  GOVERNANCE CONTROLS                                                  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  POLICY LIFECYCLE (governed change)                             │ │
│  │                                                                │ │
│  │  DRAFT → TEST → COMPARE → APPROVE → ACTIVATE → (ROLLBACK)    │ │
│  │                                                                │ │
│  │  Draft:    Risk analyst creates/edits policy YAML              │ │
│  │  Test:     Run against historic applicants in shadow mode      │ │
│  │  Compare:  Show: "X decisions would change, impact: Y"        │ │
│  │  Approve:  Authorized approver signs off (recorded)            │ │
│  │  Activate: New version becomes live (effective_date)           │ │
│  │  Rollback: Instant revert to previous version (1 click)       │ │
│  │                                                                │ │
│  │  Every transition logged with: who, when, why                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  DECISION GOVERNANCE                                           │ │
│  │                                                                │ │
│  │  Principle: No automated decision without traceable authority   │ │
│  │                                                                │ │
│  │  Auto-decisions (APPROVE/DECLINE):                             │ │
│  │  • Authority derived from active, approved policy version      │ │
│  │  • Every auto-decision cites policy_version + rule_ids         │ │
│  │  • Approval rate monitored — drift alerts if unexpected shift  │ │
│  │                                                                │ │
│  │  REFER decisions:                                              │ │
│  │  • Routed to authorized reviewer (role-based)                  │ │
│  │  • Reviewer sees: evidence packet + agent reasoning + score    │ │
│  │  • Override requires: actor identity + written reason           │ │
│  │  • Override logged permanently (cannot be deleted)             │ │
│  │                                                                │ │
│  │  Escalation:                                                   │ │
│  │  • Loan amount > threshold → requires senior reviewer         │ │
│  │  • Policy exception → requires risk committee sign-off         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  HUMAN-IN-THE-LOOP CONTROLS                                    │ │
│  │                                                                │ │
│  │  When humans MUST be involved:                                 │ │
│  │  ├── Policy change activation (always)                         │ │
│  │  ├── REFER case resolution (always)                            │ │
│  │  ├── Override of auto-decision (always logged)                 │ │
│  │  ├── System alert acknowledgment (drift, error spike)          │ │
│  │  └── Model/agent prompt changes (engineering + risk sign-off)  │ │
│  │                                                                │ │
│  │  When humans are NOT needed:                                   │ │
│  │  ├── Clear APPROVE (all agents agree, score well above)        │ │
│  │  ├── Clear DECLINE (hard rule triggered)                       │ │
│  │  └── Explanation generation (derived from lineage)             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 Audit & Compliance

```
┌──────────────────────────────────────────────────────────────────────┐
│  AUDIT TRAIL (DECISION LINEAGE)                                       │
│                                                                      │
│  Every decision produces an immutable record:                        │
│                                                                      │
│  {                                                                   │
│    "decision_id": "uuid",                                            │
│    "timestamp": "ISO-8601",                                          │
│    "applicant_id": "masked",                                         │
│    "product": "personal_loan",                                       │
│                                                                      │
│    // What was the input?                                            │
│    "evidence_snapshot": { ... full packet at decision time ... },     │
│    "evidence_quality": { "missing": [...], "stale": [...] },         │
│                                                                      │
│    // What policy applied?                                           │
│    "policy_version": "2.1",                                          │
│    "policy_hash": "sha256:abc...",                                   │
│    "segment": "personal_loan",                                       │
│                                                                      │
│    // How did agents reason?                                         │
│    "agent_assessments": {                                            │
│      "eligibility": { "result": "PASS", ... },                       │
│      "affordability": { "result": {...}, "confidence": 0.85 },       │
│      "risk": { "result": {...}, "confidence": 0.78 }                 │
│    },                                                                │
│    "agent_messages": [ ... collaboration log ... ],                   │
│                                                                      │
│    // What was the math?                                             │
│    "scoring": {                                                      │
│      "component_scores": { ... },                                    │
│      "weights_applied": { ... },                                     │
│      "final_score": 0.72,                                            │
│      "threshold_used": { "approve": 0.70 },                          │
│      "hard_rules_checked": [...],                                    │
│      "hard_rules_triggered": []                                      │
│    },                                                                │
│                                                                      │
│    // What was decided?                                              │
│    "outcome": "APPROVE",                                             │
│    "decisive_factor": "score_above_threshold",                       │
│    "explanation_generated": { ... three views ... },                  │
│                                                                      │
│    // Performance                                                    │
│    "latency_ms": 12400,                                              │
│    "stage_timings": { "ingest": 2100, "reason": 8200, ... },         │
│                                                                      │
│    // Human actions (if any)                                         │
│    "human_actions": [],                                              │
│    "override": null                                                   │
│  }                                                                   │
│                                                                      │
│  Properties:                                                         │
│  • Immutable (append-only ledger)                                    │
│  • Replayable (same inputs + same policy version → same outcome)     │
│  • Searchable (by applicant, date range, outcome, policy version)    │
│  • Tamper-evident (hash chain or signed entries)                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.4 Compliance Considerations

```
┌──────────────────────────────────────────────────────────────────────┐
│  REGULATORY ALIGNMENT                                                 │
│                                                                      │
│  Principle                    │ How Architecture Addresses            │
│  ────────────────────────────┼────────────────────────────────────── │
│  Right to explanation         │ Three-tier explanation from lineage   │
│  (adverse action notice)     │ Customer view = plain language why    │
│                              │                                        │
│  Non-discrimination          │ No protected attributes in LLM context│
│                              │ Score based on financial factors only  │
│                              │ Outcome monitoring by demographic      │
│                              │ (at scale — not in hackathon)         │
│                              │                                        │
│  Data minimization           │ Only decision-relevant fields passed  │
│                              │ PII masked before LLM processing      │
│                              │                                        │
│  Right to human review       │ REFER path = guaranteed human review  │
│                              │ Override mechanism with accountability │
│                              │                                        │
│  Record keeping              │ Immutable decision ledger             │
│                              │ Policy version history                 │
│                              │ Full evidence snapshot preserved       │
│                              │                                        │
│  Model governance            │ LLM doesn't make final decision       │
│  (AI as tool, not           │ Scoring is deterministic math          │
│   decision-maker)           │ LLM = assessor, not approver           │
│                              │ Policy authored by humans              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Complete Security Flow (Request Lifecycle)

```
  Client Request
       │
       ▼
  ┌─────────────┐
  │ API Gateway │─── Auth (JWT) ─── Rate Limit ─── Input Validation
  └──────┬──────┘
         │ authenticated, validated
         ▼
  ┌─────────────────┐
  │ Evidence Ingest  │─── PII masking applied ─── safe_for_llm filtering
  └──────┬──────────┘
         │ sanitized evidence packet
         ▼
  ┌─────────────────┐
  │ Agent Reasoning  │─── No raw PII ─── Schema-constrained output
  │ (LLM boundary)  │─── No external access ─── Output validated
  └──────┬──────────┘
         │ structured assessments (validated)
         ▼
  ┌─────────────────┐
  │ Scoring Engine   │─── Deterministic ─── Policy version locked
  └──────┬──────────┘
         │ decision + lineage
         ▼
  ┌─────────────────┐
  │ Decision Ledger  │─── Append-only ─── Signed ─── Full PII encrypted
  └──────┬──────────┘
         │
         ▼
  ┌─────────────────┐
  │ Response         │─── No PII in response ─── Explanation only
  └─────────────────┘
```

---

## 6. What This Means for Hackathon Build

### Must implement (proves the story):
- PII masking before LLM (even with mock data — shows the pattern)
- Policy versioning (effective_date, version field)
- Immutable decision record (in-memory list, but structured correctly)
- Explanation from lineage (not free-form LLM generation)
- Role-based policy edit vs approve (show separation in UI)

### Show in architecture but skip implementation:
- Full RBAC system (mention, don't build)
- Hash-chain tamper evidence (mention, show structure)
- Drift monitoring (mention as production concern)
- Encrypted storage (mock data, no real secrets)

### Demo talking points:
- "LLM never sees PII — here's the masking step"
- "Decision is math, not AI opinion — LLM assesses, rules decide"
- "Policy change requires approval — editor ≠ approver"
- "Every decision has full lineage — replayable, auditable"
- "If agents disagree, human decides — not the machine"
