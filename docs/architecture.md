# Credit Genie — Architecture (Deep Agents / LangChain)

## 1. High-Level Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend (React + Vite)"]
        UI[Decision Dashboard]
        PipelineViz[Pipeline Visualization]
        AgentChat[Agent Conversation Stream]
        PolicyEditor[Policy Editor]
    end

    subgraph DeepAgents["Deep Agents Harness"]
        Orchestrator[Main Agent - Orchestrator]
        
        subgraph SubAgents["Sub-Agents"]
            Eligibility[Eligibility Agent]
            Affordability[Affordability Agent]
            Risk[Risk Agent]
        end

        subgraph Skills["Skills"]
            PolicySkill[/skills/credit-policy/]
            EvidenceSkill[/skills/evidence-rules/]
            ExplainSkill[/skills/explanation/]
        end

        Planning[Planning / TODO Tool]
        ContextMgmt[Context Management]
    end

    subgraph Backend["Filesystem Backend"]
        PolicyStore[policy/*.yaml]
        EvidenceStore[evidence/{applicant}/]
        DecisionLedger[decisions/*.json]
        Memory[AGENTS.md - Persistent Memory]
    end

    subgraph Tools["Custom Tools"]
        EvidenceTools[Evidence Fetch Tools]
        ScoringTools[Scoring Tools]
        PolicyTools[Policy Management Tools]
        ExplainTools[Explanation Generator]
    end

    UI -->|SSE Stream| Orchestrator
    PolicyEditor -->|PUT /policy| PolicyTools
    Orchestrator --> Eligibility
    Orchestrator --> Affordability
    Orchestrator --> Risk
    Eligibility --> EvidenceTools
    Affordability --> EvidenceTools
    Risk --> EvidenceTools
    Orchestrator --> ScoringTools
    Orchestrator --> ExplainTools
    EvidenceTools --> EvidenceStore
    ScoringTools --> PolicyStore
    PolicyTools --> PolicyStore
    Orchestrator --> DecisionLedger
    Orchestrator --> Memory
    Skills -.->|loaded on demand| SubAgents
    Planning -.-> Orchestrator
    ContextMgmt -.-> Orchestrator
```

---

## 2. Deep Agents Component Mapping

```mermaid
graph LR
    subgraph DeepAgentsFramework["Deep Agents Framework"]
        direction TB
        DA_Main["create_deep_agent()"]
        DA_Sub["subagents=[]"]
        DA_Skills["skills=[]"]
        DA_FS["FilesystemBackend"]
        DA_Plan["Planning Tool"]
        DA_Ctx["Context Management"]
        DA_HITL["Human-in-the-Loop"]
        DA_Stream["LangGraph Streaming"]
    end

    subgraph CreditGenie["Credit Genie Usage"]
        direction TB
        CG_Orch["Orchestrator Agent"]
        CG_Agents["Eligibility / Affordability / Risk"]
        CG_Policy["Policy rules + evidence interpretation"]
        CG_Store["Policy YAML + Evidence + Ledger"]
        CG_Pipeline["Pipeline stage decomposition"]
        CG_Evidence["Evidence packet scoping per agent"]
        CG_Refer["REFER decisions + Policy approval"]
        CG_SSE["Real-time pipeline viz via SSE"]
    end

    DA_Main --> CG_Orch
    DA_Sub --> CG_Agents
    DA_Skills --> CG_Policy
    DA_FS --> CG_Store
    DA_Plan --> CG_Pipeline
    DA_Ctx --> CG_Evidence
    DA_HITL --> CG_Refer
    DA_Stream --> CG_SSE
```

---

## 3. Decision Pipeline Flow

```mermaid
flowchart TD
    Start([Application Request]) --> ModeSelect{Product Type?}
    
    ModeSelect -->|personal_loan| FullPath
    ModeSelect -->|bnpl| FastPath

    subgraph FullPath["FULL PATH (Personal Loan — 60s budget)"]
        direction TB
        FP_Ingest[Stage 1: Evidence Ingest<br/>Parallel fetch all sources<br/>~2-3s]
        FP_Elig[Stage 2a: Eligibility Gate<br/>Rules only<br/>~50ms]
        FP_EligCheck{Eligible?}
        FP_Parallel[Stage 2b: Parallel Assessment]
        FP_Afford[Affordability Agent<br/>LLM reasoning<br/>~8-15s]
        FP_Risk[Risk Agent<br/>Hybrid rules+LLM<br/>~5-10s]
        FP_Collab[Stage 2c: Collaboration Round<br/>Agents challenge/respond<br/>~3-8s]
        FP_Score[Stage 3: Scoring Engine<br/>Weighted + thresholds<br/>~50ms]
        FP_Explain[Stage 4: Explanation<br/>LLM generates from lineage<br/>~3-5s]
        
        FP_Ingest --> FP_Elig
        FP_Elig --> FP_EligCheck
        FP_EligCheck -->|PASS| FP_Parallel
        FP_EligCheck -->|FAIL| FP_Score
        FP_Parallel --> FP_Afford
        FP_Parallel --> FP_Risk
        FP_Afford --> FP_Collab
        FP_Risk --> FP_Collab
        FP_Collab --> FP_Score
        FP_Score --> FP_Explain
    end

    subgraph FastPath["FAST PATH (BNPL — 2s budget)"]
        direction TB
        BP_Ingest[Stage 1: Cached Evidence Lookup<br/>~50-100ms]
        BP_Rules[Stage 2: All Rules in Parallel<br/>Eligibility + Affordability + Risk<br/>~30ms]
        BP_Score[Stage 3: Scoring<br/>~10ms]
        BP_Template[Stage 4: Template Explanation<br/>~10ms]
        
        BP_Ingest --> BP_Rules
        BP_Rules --> BP_Score
        BP_Score --> BP_Template
    end

    FullPath --> Decision([Decision Record])
    FastPath --> Decision
    Decision --> Ledger[(Audit Ledger)]
```

---

## 4. Agent Collaboration Protocol

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant E as Eligibility Agent
    participant A as Affordability Agent
    participant R as Risk Agent
    participant S as Scoring Engine

    Note over O: Stage 2 begins
    
    O->>E: assess(evidence)
    E-->>O: PASS (score_band: good, file_age: 4.2yr)
    
    Note over O: Eligibility passed — run Afford + Risk parallel
    
    par Parallel Assessment
        O->>A: assess(evidence)
        O->>R: assess(evidence)
    end

    R-->>R: Detects irregular deposits
    R->>A: FLAG_CONCERN: "3 large deposits inconsistent with salary"
    
    Note over A: Re-evaluates with risk context
    A-->>A: Reassess income stability
    A->>O: ASSESSMENT: adequate (DTI 38%, confidence: 0.82)
    A->>O: Note: "Deposits explained as freelance, confidence lowered"
    
    R->>O: ASSESSMENT: moderate risk (score: 0.35)
    
    Note over O: Check consensus
    O->>O: Agents agree? Gap < 0.4 ✓
    
    O->>S: evaluate(assessments, policy)
    S-->>O: APPROVE (score: 0.72)
```

---

## 5. Agent Disagreement → REFER

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant A as Affordability Agent
    participant R as Risk Agent
    participant S as Scoring Engine

    par Parallel Assessment
        O->>A: assess(evidence)
        O->>R: assess(evidence)
    end

    R->>A: FLAG_CONCERN: "Irregular deposits, possible layering"
    
    A->>O: ASSESSMENT: uncertain (confidence: 0.55)
    R->>O: ASSESSMENT: elevated risk (confidence: 0.80)
    
    Note over O: Consensus check
    O->>O: Affordability confidence 0.55 < threshold 0.6
    O->>O: Agents disagree on risk level
    
    O->>S: evaluate(assessments, policy)
    S-->>O: REFER (agent_disagreement + low_confidence)
    
    Note over O: Generate reviewer packet
    O->>O: Bundle: evidence + both agent views + recommendation
    O-->>O: Save to decisions/ with REFER status
```

---

## 6. Policy Change Lifecycle

```mermaid
flowchart LR
    Draft[DRAFT<br/>Risk analyst edits YAML] 
    --> Validate[VALIDATE<br/>Schema + conflict check]
    --> Simulate[SIMULATE<br/>Run against N applicants<br/>Show impact diff]
    --> Approve[APPROVE<br/>Authorized approver signs]
    --> Activate[ACTIVATE<br/>Set effective_date<br/>Becomes live]
    --> Monitor[MONITOR<br/>Watch approval rate drift]

    Activate -.->|If problem| Rollback[ROLLBACK<br/>Instant revert<br/>Previous version active]
    Rollback -.-> Monitor
```

```mermaid
sequenceDiagram
    participant RA as Risk Analyst
    participant UI as Policy Editor
    participant PS as Policy Service
    participant Sim as Simulation Engine
    participant AP as Approver
    participant Live as Live System

    RA->>UI: Edit DTI threshold (40% → 50%)
    UI->>PS: PUT /policy/update (new YAML + reason)
    PS->>PS: Validate schema, detect conflicts
    PS-->>UI: Draft v2.2 created

    RA->>UI: "Simulate impact"
    UI->>Sim: POST /simulate (draft v2.2, all applicants)
    Sim->>Sim: Re-run scoring with old vs new policy
    Sim-->>UI: "2/5 decisions would change"

    RA->>AP: Request approval
    AP->>PS: POST /policy/activate (v2.2, approved_by)
    PS->>Live: New policy active
    Live-->>Live: All new decisions use v2.2

    Note over Live: If approval rate drifts...
    Live->>AP: Alert: rate shifted 15%
    AP->>PS: POST /policy/rollback (to v2.1)
    PS->>Live: Reverted to v2.1
```

---

## 7. Evidence Ingest Flow

```mermaid
flowchart TD
    Request([Applicant ID + Product]) --> Collector[Evidence Collector]
    
    Collector --> |parallel| Bureau[Bureau Adapter]
    Collector --> |parallel| Income[Income Adapter]
    Collector --> |parallel| Exposure[Exposure Adapter]
    Collector --> |parallel| Delinquency[Delinquency Adapter]
    
    Bureau --> |credit_score, exposures, history| Packet
    Income --> |monthly_income, employer, bank_tx| Packet
    Exposure --> |total_exposure, bnpl_count| Packet
    Delinquency --> |max_dpd, dpd_counts| Packet
    
    Packet[Evidence Packet]
    
    Packet --> QualityCheck{Quality Check}
    QualityCheck --> |all present| Complete[Complete Packet]
    QualityCheck --> |source timeout| Partial[Partial Packet<br/>missing fields flagged]
    QualityCheck --> |stale data| Stale[Stale Packet<br/>freshness warning]
    
    Complete --> PIIMask[PII Masking<br/>safe_for_llm filter]
    Partial --> PIIMask
    Stale --> PIIMask
    
    PIIMask --> Agents[To Agent Stage]
```

---

## 8. Scoring & Decision Logic

```mermaid
flowchart TD
    Assessments([Agent Assessments]) --> HardRules{Hard Rules Check}
    
    HardRules -->|"max_dpd >= 90"| InstantDecline[DECLINE<br/>reason: SEVERE_DELINQUENCY]
    HardRules -->|"DTI > 60%"| InstantDecline2[DECLINE<br/>reason: UNAFFORDABLE]
    HardRules -->|"credit_history < 6mo"| InstantRefer[REFER<br/>reason: THIN_FILE]
    HardRules -->|No hard rule triggered| Consensus
    
    Consensus{Agents Agree?}
    Consensus -->|"Score gap > 0.4 OR<br/>confidence < 0.6"| DisagreeRefer[REFER<br/>reason: CONFLICTING_SIGNALS]
    Consensus -->|Agents aligned| WeightedScore
    
    WeightedScore[Compute Weighted Score<br/>score = Σ weight_i × agent_score_i]
    
    WeightedScore --> Threshold{Apply Thresholds}
    Threshold -->|"score >= approve_threshold"| Approve[APPROVE]
    Threshold -->|"score <= decline_threshold"| Decline[DECLINE]
    Threshold -->|"between thresholds"| Refer[REFER]
    
    Approve --> Lineage[Record Decision Lineage]
    Decline --> Lineage
    Refer --> Lineage
    InstantDecline --> Lineage
    InstantDecline2 --> Lineage
    InstantRefer --> Lineage
    DisagreeRefer --> Lineage
    
    Lineage --> Explain[Generate Explanation<br/>from lineage factors]
```

---

## 9. Explanation Generation

```mermaid
flowchart TD
    Lineage([Decision Lineage<br/>agents + scores + rules + evidence]) --> Router{Audience?}
    
    Router -->|Customer| CustomerView[Customer View<br/>Plain language<br/>Actionable next steps<br/>No internal details]
    Router -->|Reviewer| ReviewerView[Reviewer View<br/>Factor detail<br/>Agent conversation<br/>Recommendation]
    Router -->|Audit| AuditView[Audit View<br/>Full JSON lineage<br/>Replay inputs<br/>Policy version + hash]
    
    CustomerView --> LLM[LLM Polish<br/>Humanize from structured data]
    ReviewerView --> Template[Structured Template<br/>Fill from lineage]
    AuditView --> Raw[Raw JSON<br/>No transformation]
    
    LLM --> Validate{Matches lineage?}
    Validate -->|Yes| Output([Final Explanation])
    Validate -->|No| Fallback[Fallback to template]
    Fallback --> Output
    Template --> Output
    Raw --> Output
```

---

## 10. Real-Time Pipeline Visualization (SSE)

```mermaid
sequenceDiagram
    participant Client as Frontend
    participant API as FastAPI (SSE)
    participant Orch as Orchestrator
    participant Agents as Sub-Agents

    Client->>API: POST /api/decide (applicant, product)
    API->>Orch: Start pipeline
    
    Orch-->>API: event: stage_start {stage: "ingest"}
    API-->>Client: SSE: stage_start (ingest)
    
    Note over Orch: Parallel evidence fetch...
    
    Orch-->>API: event: stage_complete {stage: "ingest", items: 12}
    API-->>Client: SSE: stage_complete (ingest)
    
    Orch-->>API: event: stage_start {stage: "reason"}
    API-->>Client: SSE: stage_start (reason)
    
    Orch->>Agents: Run eligibility
    Agents-->>Orch: Message: "PASS — score 680"
    Orch-->>API: event: agent_message
    API-->>Client: SSE: agent_message (eligibility)
    
    Orch->>Agents: Run affordability + risk
    Agents-->>Orch: Message: "Analyzing income..."
    Orch-->>API: event: agent_message
    API-->>Client: SSE: agent_message (affordability)
    
    Agents-->>Orch: Message: "Flag: irregular deposits"
    Orch-->>API: event: agent_message
    API-->>Client: SSE: agent_message (risk → affordability)
    
    Agents-->>Orch: Message: "Reassessed, adequate"
    Orch-->>API: event: agent_message
    API-->>Client: SSE: agent_message (affordability)
    
    Orch-->>API: event: stage_complete {stage: "reason"}
    API-->>Client: SSE: stage_complete (reason)
    
    Orch-->>API: event: stage_complete {stage: "score", outcome: "APPROVE"}
    API-->>Client: SSE: stage_complete (score)
    
    Orch-->>API: event: decision_made {full record}
    API-->>Client: SSE: decision_made
    
    API-->>Client: SSE: done
```

---

## 11. BNPL vs Personal Loan — Execution Mode Comparison

```mermaid
graph TB
    subgraph PersonalLoan["Personal Loan (Full Path)"]
        direction TB
        PL_Budget["⏱ Budget: 60 seconds"]
        PL_Evidence["Evidence: Live fetch, all sources"]
        PL_Agents["Agents: LLM-powered reasoning"]
        PL_Collab["Collaboration: Agents challenge each other"]
        PL_Explain["Explanation: LLM-generated narrative"]
        PL_Refer["REFER: Judgment calls allowed"]
    end

    subgraph BNPL["BNPL (Fast Path)"]
        direction TB
        BP_Budget["⏱ Budget: 2 seconds"]
        BP_Evidence["Evidence: Cached/pre-computed only"]
        BP_Agents["Agents: Rules-only, no LLM"]
        BP_Collab["Collaboration: None"]
        BP_Explain["Explanation: Template fill"]
        BP_Refer["REFER: Only hard triggers"]
    end

    subgraph Shared["Shared Across Both"]
        direction TB
        S_Policy["Same policy config"]
        S_Schema["Same evidence schema"]
        S_Ledger["Same audit ledger format"]
        S_HardRules["Same hard rules"]
    end

    PersonalLoan --- Shared
    BNPL --- Shared
```

---

## 12. Security & Governance Flow

```mermaid
flowchart TD
    subgraph DataProtection["Layer 1: Data Protection"]
        Request([Raw Request with PII]) --> Mask[PII Masking]
        Mask --> SafePacket[LLM-Safe Evidence Packet<br/>No names, no IDs, no addresses]
        Mask --> FullPacket[Full Packet<br/>Encrypted at rest<br/>Audit only]
    end

    subgraph LLMContainment["Layer 2: LLM Containment"]
        SafePacket --> LLM[LLM Agents]
        LLM --> SchemaValidate[Schema Validation<br/>Structured output enforced]
        SchemaValidate --> |Valid| Assessment[Validated Assessment]
        SchemaValidate --> |Invalid| Reject[Reject + Retry]
        LLM -.-x|"❌ No access"| External[External Systems]
        LLM -.-x|"❌ No access"| PolicyMutate[Policy Modification]
    end

    subgraph Governance["Layer 3: Governance"]
        Assessment --> Scoring[Deterministic Scoring<br/>Math only, no LLM]
        Scoring --> Decision([Decision])
        Decision --> ImmutableLog[Immutable Audit Log<br/>Append-only, signed]
    end

    subgraph Access["Layer 4: Access Control"]
        PolicyEdit[policy_editor] -->|draft only| PolicyDraft[Draft Policy]
        PolicyApprove[policy_approver] -->|activate/rollback| PolicyLive[Live Policy]
        Reviewer[reviewer] -->|resolve REFER| Override[Override + Reason]
        Auditor[auditor] -->|read-only| ImmutableLog
    end
```

---

## 13. Timeout & Degradation Strategy

```mermaid
flowchart TD
    Start([Pipeline Start]) --> IngestTimeout{Evidence fetch<br/>within budget?}
    
    IngestTimeout -->|All sources OK| FullEvidence[Complete Evidence]
    IngestTimeout -->|Source timeout| PartialEvidence[Partial Evidence<br/>+ missing flags]
    
    FullEvidence --> AgentRun[Run Agents]
    PartialEvidence --> AgentRun
    
    AgentRun --> LLMTimeout{LLM response<br/>within budget?}
    
    LLMTimeout -->|OK| FullAssessment[Full LLM Assessment]
    LLMTimeout -->|Timeout| Fallback[Fallback to Rules-Only<br/>for that agent]
    
    FullAssessment --> CollabTimeout{Collaboration<br/>within budget?}
    Fallback --> Scoring
    
    CollabTimeout -->|OK| CollabDone[Collaboration Complete]
    CollabTimeout -->|Timeout| SkipCollab[Skip Collaboration<br/>Use individual assessments]
    
    CollabDone --> Scoring[Scoring Engine<br/>Always completes < 100ms]
    SkipCollab --> Scoring
    
    Scoring --> ExplainTimeout{Explanation LLM<br/>within budget?}
    
    ExplainTimeout -->|OK| RichExplain[Rich LLM Explanation]
    ExplainTimeout -->|Timeout| TemplateExplain[Template Explanation<br/>Fill from lineage]
    
    RichExplain --> Done([Decision Complete])
    TemplateExplain --> Done
    
    Note1[/"Every degradation is safe:<br/>partial evidence → REFER<br/>LLM timeout → rules fallback<br/>Never auto-APPROVE on degradation"/]
```

---

## 14. Filesystem Backend Structure

```mermaid
graph TD
    subgraph Workspace["workspace/ (FilesystemBackend root)"]
        subgraph Policy["policy/"]
            PL_Active["personal_loan_active.yaml"]
            BNPL_Active["bnpl_active.yaml"]
            History["history/<br/>personal_loan_v2.0.yaml<br/>personal_loan_v1.9.yaml<br/>..."]
        end

        subgraph Evidence["evidence/{applicant_id}/"]
            Bureau["bureau.json"]
            Income["income.json"]
            BankTx["bank_statements.json"]
            Exposure["exposure.json"]
            Delinquency["delinquency.json"]
        end

        subgraph Decisions["decisions/"]
            D1["d-2026-07-11-001.json<br/>(APPROVE, full lineage)"]
            D2["d-2026-07-11-002.json<br/>(REFER, full lineage)"]
            D3["d-2026-07-11-003.json<br/>(DECLINE, full lineage)"]
        end

        subgraph SkillsDir["skills/"]
            PolSkill["credit-policy/<br/>eligibility rules<br/>affordability thresholds<br/>risk patterns"]
            EvSkill["evidence-rules/<br/>freshness limits<br/>confidence mapping<br/>missing data handling"]
            ExSkill["explanation/<br/>templates<br/>reason codes<br/>audience formatting"]
        end

        AgentsMD["AGENTS.md<br/>(Persistent memory)"]
    end
```

---

## 15. Demo Architecture (End-to-End)

```mermaid
flowchart LR
    subgraph User["Demo User"]
        Select[Select Applicant]
        Watch[Watch Pipeline]
        EditPolicy[Edit Policy]
        Compare[Compare Outcomes]
    end

    subgraph System["Credit Genie"]
        API[FastAPI + SSE]
        DA[Deep Agents Orchestrator]
        Agents[3 Sub-Agents]
        FS[Filesystem Backend]
    end

    subgraph Outputs["Visible Outputs"]
        Pipeline[Pipeline Stage Progress]
        Chat[Agent Conversation]
        Decision[Decision Card]
        Score[Score Breakdown]
        Explain[Explanation Views]
        Audit[Audit Trail]
        Sim[Simulation Results]
    end

    Select -->|POST /decide| API
    API -->|stream| DA
    DA --> Agents
    Agents --> FS
    DA -->|SSE events| Pipeline
    DA -->|SSE events| Chat
    DA -->|final| Decision
    DA -->|final| Score
    DA -->|final| Explain
    DA -->|save| Audit

    EditPolicy -->|PUT /policy| API
    API -->|simulate| Sim
    Compare --> Sim
```

---

## 16. Tech Stack

```mermaid
graph TD
    subgraph Runtime["Python Runtime"]
        DeepAgents["deepagents v0.6+"]
        LangGraph["LangGraph (streaming, persistence)"]
        FastAPI["FastAPI (API + SSE)"]
        Pydantic["Pydantic (validation)"]
    end

    subgraph LLM["LLM Layer"]
        Claude["Claude API<br/>anthropic:claude-sonnet-4-6"]
        StructuredOutput["Structured Output<br/>(tool_use schema enforcement)"]
    end

    subgraph Frontend["Frontend"]
        React["React + Vite"]
        Tailwind["Tailwind CSS"]
        Framer["Framer Motion<br/>(pipeline animations)"]
        EventSource["EventSource (SSE)"]
    end

    subgraph Storage["Storage (No DB)"]
        YAML["YAML (policy configs)"]
        JSON["JSON (evidence fixtures + decisions)"]
        MD["Markdown (AGENTS.md memory)"]
    end

    DeepAgents --> LangGraph
    DeepAgents --> Claude
    Claude --> StructuredOutput
    FastAPI --> DeepAgents
    React --> FastAPI
    EventSource --> FastAPI
    DeepAgents --> YAML
    DeepAgents --> JSON
    DeepAgents --> MD
```
