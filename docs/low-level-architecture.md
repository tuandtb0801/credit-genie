# Credit Genie — Low-Level Architecture (Deep Agents)

## 1. Module Dependency Graph

```mermaid
graph TD
    subgraph Entrypoint["Entrypoint"]
        Main["main.py<br/>FastAPI app + SSE endpoints"]
    end

    subgraph API["api/"]
        Routes["routes.py<br/>REST endpoints"]
        Events["events.py<br/>SSE streaming"]
        PolicyRoutes["policy_routes.py<br/>Policy CRUD + simulate"]
    end

    subgraph Agent["agent/"]
        AgentConfig["config.py<br/>create_deep_agent() setup"]
        SubAgentDefs["subagents.py<br/>Eligibility, Affordability, Risk definitions"]
        Prompts["prompts.py<br/>System prompts per agent"]
    end

    subgraph ToolsDef["tools/"]
        EvidenceTools["evidence.py<br/>fetch_bureau, fetch_income,<br/>fetch_exposure, fetch_delinquency"]
        ScoringTools["scoring.py<br/>evaluate_rules, compute_dti,<br/>compute_weighted_score, apply_thresholds"]
        PolicyTools["policy.py<br/>load_active, simulate, activate, rollback"]
        ExplainTools["explanation.py<br/>generate_explanation"]
    end

    subgraph SkillsDir["skills/"]
        CreditPolicy["credit-policy/"]
        EvidenceRules["evidence-rules/"]
        ExplanationSkill["explanation/"]
        FraudSignals["fraud-signals/"]
    end

    subgraph Workspace["workspace/ (FilesystemBackend)"]
        Policy["policy/*.yaml"]
        Evidence["evidence/{applicant}/*.json"]
        Decisions["decisions/*.json"]
        AgentsMD["AGENTS.md"]
    end

    Main --> Routes
    Main --> Events
    Main --> PolicyRoutes
    Routes --> AgentConfig
    Events --> AgentConfig
    PolicyRoutes --> PolicyTools
    AgentConfig --> SubAgentDefs
    AgentConfig --> Prompts
    SubAgentDefs --> EvidenceTools
    SubAgentDefs --> ScoringTools
    EvidenceTools --> Evidence
    ScoringTools --> Policy
    PolicyTools --> Policy
    ExplainTools --> Decisions
    AgentConfig --> SkillsDir
    AgentConfig --> Workspace
```

---

## 2. Deep Agents Runtime Internals

```mermaid
graph TD
    subgraph DeepAgentsRuntime["Deep Agents Runtime (LangGraph)"]
        direction TB
        
        subgraph StateGraph["State Graph"]
            Init["Initial State<br/>{messages, context, plan}"]
            ToolLoop["Tool-Calling Loop<br/>LLM → tool_call → result → LLM"]
            SubAgentNode["Sub-Agent Node<br/>Isolated context window"]
            PlanNode["Planning Node<br/>TODO decomposition"]
            ContextNode["Context Management Node<br/>Summarize / offload"]
        end

        subgraph Checkpointing["Checkpointing"]
            CP_Save["Save state after each step"]
            CP_Resume["Resume from last checkpoint on crash"]
            CP_Stream["Stream intermediate state to client"]
        end

        subgraph Memory["Persistent Memory"]
            ShortTerm["Short-term: conversation messages"]
            LongTerm["Long-term: AGENTS.md<br/>Cross-session recall"]
            Store["Store backend:<br/>Filesystem (hackathon)<br/>PostgreSQL (production)"]
        end
    end

    Init --> PlanNode
    PlanNode --> ToolLoop
    ToolLoop --> SubAgentNode
    SubAgentNode --> ToolLoop
    ToolLoop --> ContextNode
    ContextNode --> ToolLoop
    ToolLoop --> CP_Save
    CP_Save --> CP_Stream
```

---

## 3. Request Lifecycle (Full Path — Personal Loan)

```mermaid
sequenceDiagram
    participant C as Client
    participant F as FastAPI
    participant DA as Deep Agents Runtime
    participant LG as LangGraph State
    participant LLM as Claude API
    participant E as Eligibility SubAgent
    participant A as Affordability SubAgent
    participant R as Risk SubAgent
    participant T as Tools (MCP)
    participant FS as Filesystem Backend

    C->>F: POST /api/decide {applicant_id, product: "personal_loan"}
    F->>DA: invoke(messages: "Decide for APP-001, personal_loan")
    
    Note over DA,LG: PLANNING PHASE
    DA->>LLM: System prompt + task
    LLM-->>DA: Plan: [1. ingest, 2. eligibility, 3. afford+risk, 4. score, 5. explain]
    DA->>LG: Save plan to state

    Note over DA,T: STAGE 1: EVIDENCE INGEST
    DA->>LLM: "Execute stage 1: gather evidence"
    LLM-->>DA: tool_call: fetch_bureau_data(APP-001)
    DA->>T: Execute tool
    T->>FS: Read evidence/APP-001/bureau.json
    FS-->>T: {credit_score: 680, ...}
    T-->>DA: Tool result
    DA-->>F: SSE: stage_start(ingest)
    
    LLM-->>DA: tool_call: fetch_income_data(APP-001)
    DA->>T: Execute tool
    T-->>DA: Tool result
    
    LLM-->>DA: tool_call: fetch_exposure_data(APP-001)
    DA->>T: Execute tool
    T-->>DA: Tool result

    LLM-->>DA: tool_call: fetch_delinquency_data(APP-001)
    DA->>T: Execute tool
    T-->>DA: Tool result
    DA-->>F: SSE: stage_complete(ingest, items: 12)

    Note over DA,E: STAGE 2a: ELIGIBILITY GATE
    DA->>E: Delegate: "Check eligibility" + evidence context
    E->>LLM: Eligibility prompt + evidence
    LLM-->>E: tool_call: evaluate_rules(...)
    E->>T: Execute
    T-->>E: Rules results
    LLM-->>E: tool_call: check_score_band(680)
    E->>T: Execute
    T-->>E: Band: "good", meets minimum
    E-->>DA: Assessment: PASS (confidence: 1.0)
    DA-->>F: SSE: agent_message(eligibility: PASS)

    Note over DA,R: STAGE 2b: PARALLEL ASSESSMENT
    par Parallel Sub-Agent Delegation
        DA->>A: Delegate: "Assess affordability" + evidence
        DA->>R: Delegate: "Assess risk" + evidence
    end

    R->>LLM: Risk prompt + evidence
    LLM-->>R: Detects irregular deposits
    R-->>DA: Message: FLAG_CONCERN → Affordability
    DA->>A: Forward: "Risk flags irregular deposits"
    DA-->>F: SSE: agent_message(risk → affordability: flag)

    A->>LLM: Affordability prompt + evidence + risk concern
    LLM-->>A: Re-evaluates with context
    A-->>DA: Assessment: adequate (DTI: 38%, confidence: 0.82)
    DA-->>F: SSE: agent_message(affordability: adequate)

    R-->>DA: Assessment: moderate (risk_score: 0.35)
    DA-->>F: SSE: agent_message(risk: moderate)

    Note over DA,T: STAGE 3: SCORING
    DA->>LLM: "Score the assessments"
    LLM-->>DA: tool_call: load_active_policy("personal_loan")
    DA->>T: Execute
    T->>FS: Read policy/personal_loan_active.yaml
    T-->>DA: Policy config

    LLM-->>DA: tool_call: compute_weighted_score(1.0, 0.78, 0.65, weights)
    DA->>T: Execute
    T-->>DA: {final_score: 0.72}

    LLM-->>DA: tool_call: apply_thresholds(0.72, {approve: 0.70, decline: 0.35})
    DA->>T: Execute
    T-->>DA: APPROVE
    DA-->>F: SSE: stage_complete(score, outcome: APPROVE)

    Note over DA,T: STAGE 4: EXPLANATION
    DA->>LLM: "Generate explanation from decision lineage"
    LLM-->>DA: tool_call: generate_explanation(lineage)
    DA->>T: Execute
    T-->>DA: {customer: "...", reviewer: "...", audit: {...}}
    DA-->>F: SSE: explanation_ready

    Note over DA,FS: SAVE DECISION RECORD
    DA->>LLM: "Save decision to ledger"
    LLM-->>DA: tool_call: write_file("decisions/d-001.json", record)
    DA->>FS: Write
    DA-->>F: SSE: decision_made(full record)
    F-->>C: SSE: done
```

---

## 4. Request Lifecycle (Fast Path — BNPL)

```mermaid
sequenceDiagram
    participant C as Client
    participant F as FastAPI
    participant A as BNPL Reasoning Agent
    participant T as Tools
    participant FS as Filesystem

    C->>F: POST /api/decide {applicant_id, product: "bnpl"}
    F->>T: Fetch four cached evidence sources + active policy
    T-->>F: Evidence packet + policy
    F->>F: Eligibility, hard rules, DTI, risk anchor
    F->>A: Compact evidence + source quality + deterministic anchors
    A-->>F: Structured assessment + confidence + evidence refs
    F->>F: Deterministic rules, score, threshold, template explanation
    F->>FS: Write decision record
    F-->>C: {outcome: APPROVE, latency_ms: 1xxx}

    Note over C,FS: Target total: <2s<br/>One structured reasoning call<br/>No sub-agents<br/>No collaboration<br/>Python owns the final outcome
```

---

## 5. Sub-Agent Internal Flow

```mermaid
flowchart TD
    subgraph SubAgentLifecycle["Sub-Agent Lifecycle (per delegation)"]
        Receive["Receive delegation from Orchestrator<br/>- Task description<br/>- Scoped evidence context<br/>- Assigned tools<br/>- Loaded skills"]
        
        Receive --> Plan["Internal planning<br/>What to check, in what order"]
        
        Plan --> ToolLoop["Tool-calling loop<br/>Call tools, get results,<br/>reason about results"]
        
        ToolLoop --> IncomingMsg{Incoming message<br/>from another agent?}
        IncomingMsg -->|Yes| Process["Process message<br/>Incorporate context<br/>Possibly re-evaluate"]
        IncomingMsg -->|No| Continue
        Process --> ToolLoop
        
        Continue --> Confidence{Confidence<br/>sufficient?}
        Confidence -->|"≥ 0.6"| Submit["Submit assessment<br/>to Orchestrator"]
        Confidence -->|"< 0.6"| Flag["Flag uncertainty<br/>Request more context<br/>or ESCALATE"]
        Flag --> ToolLoop
        
        Submit --> Done["Sub-agent complete<br/>Context window released"]
    end
```

---

## 6. Context Window Management

```mermaid
flowchart TD
    subgraph ContextStrategy["Context Management Strategy"]
        direction TB
        
        subgraph Orchestrator["Orchestrator Context"]
            O_System["System prompt (~800 tokens)"]
            O_Plan["Current plan state (~200 tokens)"]
            O_Evidence["Evidence summary (~500 tokens)<br/>NOT full packet"]
            O_AgentResults["Agent assessment summaries (~300 tokens)<br/>NOT full conversation"]
            O_Policy["Active policy key fields (~200 tokens)"]
        end

        subgraph SubAgentCtx["Sub-Agent Context (Isolated)"]
            SA_System["Sub-agent system prompt (~500 tokens)"]
            SA_Skills["Loaded skills (~300 tokens)"]
            SA_Evidence["ONLY relevant evidence fields<br/>Affordability gets income+obligations<br/>Risk gets delinquency+exposure"]
            SA_Messages["Incoming messages from other agents"]
        end

        subgraph Offload["Context Offload (Deep Agents built-in)"]
            Summarize["Summarize long tool outputs<br/>before adding to context"]
            Filesystem["Write intermediate results<br/>to filesystem, reference by path"]
            Prune["Prune old messages<br/>when context nears limit"]
        end
    end

    Note1[/"Key: Sub-agents get SCOPED context.<br/>Affordability never sees delinquency raw data.<br/>Risk never sees income docs.<br/>Each agent focused on its mandate."/]
```

---

## 7. Evidence Packet Flow Through Pipeline

```mermaid
flowchart LR
    subgraph Raw["Raw Evidence (Sources)"]
        B[Bureau JSON]
        I[Income JSON]
        E[Exposure JSON]
        D[Delinquency JSON]
    end

    subgraph Collected["Collected Packet"]
        Packet["Full Evidence Packet<br/>All fields + metadata<br/>confidence, freshness, source"]
    end

    subgraph Filtered["Filtered for Agents"]
        Safe["LLM-Safe Fields Only<br/>(PII masked/removed)"]
        EligFields["Eligibility slice:<br/>credit_score, file_age"]
        AffordFields["Affordability slice:<br/>income, obligations, bank_tx"]
        RiskFields["Risk slice:<br/>delinquency, exposure, bnpl_count"]
    end

    subgraph Audit["Audit Record"]
        Full["Full snapshot<br/>All fields preserved<br/>Including PII (encrypted)"]
    end

    Raw --> Collected
    Collected --> Safe
    Safe --> EligFields
    Safe --> AffordFields
    Safe --> RiskFields
    Collected --> Full
```

---

## 8. Scoring Engine Internal Logic

```mermaid
flowchart TD
    Input["Input:<br/>Agent assessments<br/>+ Evidence packet<br/>+ Active policy"] --> Step1

    Step1["Step 1: Load hard rules<br/>from policy for segment"] --> Step2

    Step2["Step 2: Evaluate each hard rule<br/>against evidence values"] --> HardCheck

    HardCheck{Any hard rule<br/>triggered?}
    HardCheck -->|Yes| HardDecision["Immediate decision<br/>DECLINE or REFER<br/>Decisive factor = rule"]
    HardCheck -->|No| Step3

    Step3["Step 3: Check agent consensus<br/>Score gap between agents?<br/>Any confidence below threshold?"] --> ConsensusCheck

    ConsensusCheck{Agents agree?}
    ConsensusCheck -->|No| DisagreeRefer["REFER<br/>reason: CONFLICTING_SIGNALS<br/>Both viewpoints attached"]
    ConsensusCheck -->|Yes| Step4

    Step4["Step 4: Compute weighted score<br/><br/>eligibility_score × 0.25<br/>+ affordability_score × 0.40<br/>+ risk_score × 0.35<br/>= final_score"] --> Step5

    Step5["Step 5: Apply thresholds<br/>from active policy"] --> ThresholdCheck

    ThresholdCheck{Score position?}
    ThresholdCheck -->|"≥ approve (0.70)"| Approve["APPROVE"]
    ThresholdCheck -->|"≤ decline (0.35)"| Decline["DECLINE"]
    ThresholdCheck -->|"between"| Refer["REFER"]

    Approve --> Step6
    Decline --> Step6
    Refer --> Step6
    HardDecision --> Step6
    DisagreeRefer --> Step6

    Step6["Step 6: Identify decisive factors<br/>Which component had most weight?<br/>Which rule/threshold was closest?<br/>What evidence tipped it?"]

    Step6 --> Output["Output:<br/>outcome + final_score +<br/>component_scores + hard_rules_triggered +<br/>decisive_factors"]
```

---

## 9. Policy Engine Internals

```mermaid
flowchart TD
    subgraph PolicyLifecycle["Policy Version Lifecycle"]
        direction LR
        YAML["YAML File<br/>on filesystem"] --> Parse["Parse + Validate<br/>Schema check<br/>Conflict detection"]
        Parse --> Version["Assign version<br/>+ hash + effective_date"]
        Version --> Draft["Status: DRAFT<br/>Not yet active"]
        Draft --> Simulate["Run simulation<br/>Against N applicants"]
        Simulate --> Compare["Show diff:<br/>old outcome vs new"]
        Compare --> Approve["Approver signs off<br/>Record: who, when, why"]
        Approve --> Active["Status: ACTIVE<br/>Used by all new decisions"]
        Active --> Monitor["Monitor approval rate"]
        Monitor -->|Drift detected| Alert["Alert approver"]
        Alert --> Rollback["ROLLBACK<br/>Revert to previous active"]
    end
```

```mermaid
flowchart TD
    subgraph PolicyResolution["Policy Resolution at Decision Time"]
        Request["Decision request<br/>product: personal_loan"] --> FindActive
        FindActive["Find active policy<br/>for segment 'personal_loan'"] --> Load
        Load["Load YAML from<br/>policy/personal_loan_active.yaml"] --> Validate
        Validate["Validate policy integrity<br/>hash matches, not expired"] --> Extract
        Extract["Extract for decision:<br/>- weights<br/>- thresholds<br/>- hard rules<br/>- features (llm_on/off)"]
        Extract --> Lock["Lock version for this decision<br/>Record policy_version + hash<br/>in decision record"]
    end
```

---

## 10. Explanation Generator Internals

```mermaid
flowchart TD
    subgraph ExplainPipeline["Explanation Generation Pipeline"]
        Lineage["Decision Lineage<br/>(structured data)"] --> Extract

        Extract["Extract decisive factors:<br/>- Which rules fired?<br/>- Which agent drove outcome?<br/>- What evidence was key?<br/>- What threshold was hit?"]

        Extract --> Router{Product mode?}

        Router -->|"Full path (PL)"| LLMExplain
        Router -->|"Fast path (BNPL)"| TemplateExplain

        subgraph LLMExplain["LLM Explanation (Personal Loan)"]
            LLM_Prompt["Prompt LLM with:<br/>- Structured lineage<br/>- Decisive factors<br/>- Agent reasoning excerpts<br/>- Audience instructions"]
            LLM_Generate["LLM generates<br/>natural language per audience"]
            LLM_Validate["Validate:<br/>Does explanation match lineage?<br/>Any facts not in evidence?"]
            LLM_Prompt --> LLM_Generate --> LLM_Validate
            LLM_Validate -->|Pass| LLM_Output["Approved explanation"]
            LLM_Validate -->|Fail| Fallback["Fallback to template"]
        end

        subgraph TemplateExplain["Template Explanation (BNPL)"]
            T_Lookup["Look up reason_code<br/>in policy config"]
            T_Fill["Fill template with<br/>actual values from evidence"]
            T_Format["Format per audience"]
            T_Lookup --> T_Fill --> T_Format
        end

        LLM_Output --> ThreeViews
        Fallback --> TemplateExplain
        T_Format --> ThreeViews

        ThreeViews["Three Views:<br/>1. Customer (empathetic, plain language)<br/>2. Reviewer (detailed, factual)<br/>3. Audit (full JSON, machine-readable)"]
    end
```

---

## 11. SSE Event Pipeline Internals

```mermaid
flowchart TD
    subgraph EventGeneration["Event Generation"]
        Orchestrator["Orchestrator<br/>yields events at each step"]
        SubAgents["Sub-agents<br/>yield messages during reasoning"]
        Tools["Tools<br/>report execution results"]
    end

    subgraph EventBus["Internal Event Bus"]
        Queue["Async event queue<br/>ordered by timestamp"]
        Filter["Filter by subscription<br/>(per connected client)"]
    end

    subgraph SSETransport["SSE Transport"]
        Serialize["Serialize to SSE format:<br/>event: {type}<br/>data: {json}"]
        Stream["AsyncGenerator<br/>yields formatted events"]
        Keepalive["Keepalive ping<br/>every 15s if idle"]
    end

    subgraph Client["Client (EventSource)"]
        Reconnect["Auto-reconnect<br/>on disconnect"]
        StateUpdate["Update UI state<br/>per event type"]
        Terminal["Close on 'done' event"]
    end

    Orchestrator --> Queue
    SubAgents --> Queue
    Tools --> Queue
    Queue --> Filter
    Filter --> Serialize
    Serialize --> Stream
    Stream --> Keepalive
    Keepalive --> Client
    Stream --> Client
```

---

## 12. SSE Event Type Taxonomy

```mermaid
graph TD
    subgraph Events["Pipeline Event Types"]
        direction TB
        
        subgraph Lifecycle["Lifecycle Events"]
            stage_start["stage_start<br/>Which stage beginning<br/>+ mode if relevant"]
            stage_complete["stage_complete<br/>Stage finished<br/>+ timing + summary"]
            decision_made["decision_made<br/>Full decision record<br/>Final event"]
            done["done<br/>Stream complete<br/>Client should close"]
            error["error<br/>What failed<br/>+ whether recoverable"]
        end

        subgraph AgentEvents["Agent Events"]
            agent_msg["agent_message<br/>from_agent, to_agent<br/>message_type, content<br/>evidence_refs"]
        end

        subgraph MessageTypes["Agent Message Types"]
            assessment["assessment<br/>Agent submits evaluation"]
            flag_concern["flag_concern<br/>Agent raises issue"]
            request_review["request_review<br/>Ask to re-evaluate"]
            provide_context["provide_context<br/>Share finding"]
            escalate["escalate<br/>Recommend REFER"]
        end
    end

    AgentEvents --> MessageTypes
```

---

## 13. Timeout Budget Allocation

```mermaid
gantt
    title Personal Loan — Time Budget (60s total)
    dateFormat X
    axisFormat %s

    section Evidence Ingest
    Bureau fetch          :0, 2
    Income fetch          :0, 2
    Exposure fetch        :0, 1
    Delinquency fetch     :0, 1
    Timeout buffer        :2, 5

    section Agent Reasoning
    Eligibility (rules)   :5, 5
    Affordability (LLM)   :5, 20
    Risk (hybrid)         :5, 15
    Collaboration round   :20, 28

    section Scoring
    Policy load + compute :28, 28

    section Explanation
    LLM explanation       :29, 34
    Template fallback     :crit, 34, 35

    section Buffer
    Safety margin         :35, 60
```

```mermaid
gantt
    title BNPL — Time Budget (2s total)
    dateFormat X
    axisFormat %s

    section Evidence
    Cached lookup         :0, 100

    section Rules
    Eligibility rules     :100, 110
    Affordability rules   :100, 110
    Risk rules            :100, 110

    section Score
    Compute + threshold   :110, 120

    section Explain
    Template fill         :120, 130

    section Buffer
    Safety margin         :130, 2000
```

---

## 14. Error Handling & Recovery

```mermaid
flowchart TD
    subgraph Errors["Error Scenarios"]
        E1["Evidence source timeout"]
        E2["LLM API timeout"]
        E3["LLM returns invalid schema"]
        E4["Sub-agent crashes"]
        E5["Policy file corrupted"]
        E6["Checkpoint write fails"]
    end

    subgraph Recovery["Recovery Actions"]
        R1["Proceed with partial evidence<br/>+ flag missing in lineage"]
        R2["Fallback to rules-only<br/>for affected agent"]
        R3["Retry once with stricter prompt<br/>then fallback to template"]
        R4["Use last checkpoint state<br/>skip failed agent<br/>REFER if critical"]
        R5["Fail fast with clear error<br/>Do NOT make decision<br/>Alert ops team"]
        R6["Retry write<br/>Complete decision in-memory<br/>Persist on next success"]
    end

    subgraph Principle["Principles"]
        P1["NEVER auto-APPROVE on error"]
        P2["Degradation always moves<br/>toward REFER, not APPROVE"]
        P3["Every error recorded<br/>in decision lineage"]
    end

    E1 --> R1
    E2 --> R2
    E3 --> R3
    E4 --> R4
    E5 --> R5
    E6 --> R6

    R1 --> Principle
    R2 --> Principle
    R3 --> Principle
    R4 --> Principle
```

---

## 15. Data Flow — End to End (Complete)

```mermaid
flowchart TD
    subgraph Input["Input"]
        Applicant["Applicant ID + Product"]
    end

    subgraph Ingest["Stage 1: Ingest"]
        Fetch["Parallel fetch from 4 sources"]
        Normalize["Normalize to EvidencePacket<br/>+ confidence + freshness"]
        QualityFlag["Flag missing/stale/unverified"]
        PIIMask["PII masking for LLM safety"]
    end

    subgraph Reason["Stage 2: Multi-Agent Reasoning"]
        EligGate["Eligibility gate (rules)"]
        ParallelAssess["Parallel: Afford + Risk"]
        Collab["Collaboration round<br/>(if concerns flagged)"]
        Consensus["Consensus check"]
    end

    subgraph Score["Stage 3: Scoring"]
        LoadPolicy["Load active policy<br/>(versioned, hashed)"]
        HardRules["Check hard rules"]
        WeightedCalc["Weighted score computation"]
        Threshold["Apply thresholds"]
    end

    subgraph Explain["Stage 4: Explanation"]
        ExtractFactors["Extract decisive factors"]
        GenerateViews["Generate 3 audience views"]
        ValidateMatch["Validate explanation matches lineage"]
    end

    subgraph Output["Output"]
        DecisionRecord["Immutable Decision Record<br/>- outcome<br/>- score breakdown<br/>- agent reasoning<br/>- decisive factors<br/>- evidence snapshot<br/>- policy version<br/>- timing<br/>- explanation (3 views)"]
        SSEStream["SSE events (real-time)"]
        AuditLedger["Audit ledger (filesystem)"]
    end

    Input --> Ingest
    Fetch --> Normalize --> QualityFlag --> PIIMask
    Ingest --> Reason
    EligGate -->|PASS| ParallelAssess
    EligGate -->|FAIL| Score
    ParallelAssess --> Collab --> Consensus
    Reason --> Score
    LoadPolicy --> HardRules --> WeightedCalc --> Threshold
    Score --> Explain
    ExtractFactors --> GenerateViews --> ValidateMatch
    Explain --> Output

    Ingest -.->|events| SSEStream
    Reason -.->|agent messages| SSEStream
    Score -.->|decision event| SSEStream
    Explain -.->|explanation event| SSEStream
    Output --> AuditLedger
```

---

## 16. Deployment Topology

```mermaid
graph TD
    subgraph HackathonDeploy["Hackathon Deployment"]
        direction TB
        Local["Single machine<br/>or Railway/Render"]
        
        subgraph Backend["Backend Process"]
            FastAPI_H["FastAPI server"]
            DeepAgents_H["Deep Agents runtime"]
            FS_H["Filesystem backend<br/>(local disk)"]
        end

        subgraph Frontend_H["Frontend"]
            Vite_H["Vite dev server<br/>or static build"]
        end

        Claude_H["Claude API<br/>(external)"]
    end

    subgraph ProductionDeploy["Production Architecture (Future)"]
        direction TB
        
        subgraph LB["Load Balancer"]
            LB1["API Gateway<br/>Auth + Rate Limit"]
        end

        subgraph Services["Services"]
            API_P["API Service<br/>(stateless, horizontally scaled)"]
            DA_P["Deep Agents Workers<br/>(stateful, LangGraph checkpoints)"]
        end

        subgraph Persistence["Persistence"]
            PG["PostgreSQL<br/>Decision records<br/>Policy versions<br/>Agent memory"]
            Redis["Redis<br/>Evidence cache<br/>Session state"]
        end

        subgraph External["External"]
            Claude_P["Claude API"]
            Bureau_P["Real Bureau APIs"]
            Bank_P["Bank Statement APIs"]
            Fraud_P["Fraud Detection"]
        end

        subgraph Observability_P["Observability"]
            LS["LangSmith<br/>Traces + Eval"]
            Metrics["Metrics<br/>Latency, approval rate"]
            Alerts["Alerting<br/>Drift, errors, timeouts"]
        end
    end

    Vite_H --> FastAPI_H
    FastAPI_H --> DeepAgents_H
    DeepAgents_H --> FS_H
    DeepAgents_H --> Claude_H

    LB1 --> API_P
    API_P --> DA_P
    DA_P --> PG
    DA_P --> Redis
    DA_P --> Claude_P
    DA_P --> Bureau_P
    DA_P --> Bank_P
    DA_P --> Fraud_P
    DA_P --> LS
    LS --> Metrics
    Metrics --> Alerts
```
