# Credit Genie — Agent Design, Tools, MCP & A2A Protocol

## 1. Agent Roles & Behavior

```mermaid
graph TD
    subgraph Orchestrator["🎯 Main Agent (Orchestrator)"]
        O_Role["Role: Coordinate decision pipeline"]
        O_Behavior["Behavior:<br/>- Decompose application into stages<br/>- Delegate to sub-agents<br/>- Facilitate collaboration<br/>- Enforce time budgets<br/>- Save decision records"]
        O_Model["Model: claude-sonnet-4-6"]
        O_Mode["Modes: Full (PL) / Fast (BNPL)"]
    end

    subgraph Eligibility["🚪 Eligibility Agent"]
        E_Role["Role: Gate check — minimum criteria"]
        E_Behavior["Behavior:<br/>- Check score band minimum<br/>- Check credit file age<br/>- Check blacklist/fraud flags<br/>- PASS or FAIL only, no ambiguity<br/>- Never uses LLM reasoning<br/>- Fast, deterministic, rules-only"]
        E_Output["Output: PASS / FAIL + rule results"]
    end

    subgraph Affordability["💰 Affordability Agent"]
        E2_Role["Role: Can applicant service this debt?"]
        E2_Behavior["Behavior:<br/>- Compute DTI from income + obligations<br/>- Analyze bank statement patterns<br/>- Detect income stability/volatility<br/>- Flag irregular patterns<br/>- Respond to Risk agent challenges<br/>- Report confidence honestly<br/>- Lower confidence when uncertain"]
        E2_Output["Output: adequate/marginal/inadequate/uncertain<br/>+ confidence score + cited factors"]
    end

    subgraph Risk["⚠️ Risk Agent"]
        R_Role["Role: What could go wrong?"]
        R_Behavior["Behavior:<br/>- Check delinquency severity<br/>- Check exposure concentration<br/>- Detect BNPL stacking<br/>- Spot fraud signals<br/>- CHALLENGE affordability agent<br/>- Flag concerns proactively<br/>- Acts as adversarial reviewer"]
        R_Output["Output: low/moderate/elevated/high<br/>+ concerns for other agents"]
    end

    Orchestrator -->|delegates| Eligibility
    Orchestrator -->|delegates| Affordability
    Orchestrator -->|delegates| Risk
    Risk -->|challenges| Affordability
    Affordability -->|responds| Risk
```

---

## 2. Agent Communication Protocol (A2A)

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant E as Eligibility
    participant A as Affordability
    participant R as Risk

    Note over O,R: MESSAGE TYPES

    rect rgb(220, 240, 220)
        Note over E,O: ASSESSMENT<br/>Agent submits final evaluation
        E->>O: {type: assessment, result: PASS, confidence: 1.0}
    end

    rect rgb(255, 230, 230)
        Note over R,A: FLAG_CONCERN<br/>Agent raises issue to another agent
        R->>A: {type: flag_concern, content: "irregular deposits",<br/>evidence_refs: ["bank_tx_045"]}
    end

    rect rgb(230, 230, 255)
        Note over O,A: REQUEST_REVIEW<br/>Ask agent to re-evaluate
        O->>A: {type: request_review, context: "Risk sees elevated,<br/>you see adequate — reconcile?"}
    end

    rect rgb(255, 255, 220)
        Note over A,O: PROVIDE_CONTEXT<br/>Share finding with peers
        A->>O: {type: provide_context, content: "Deposits explained<br/>as freelance income"}
    end

    rect rgb(255, 220, 255)
        Note over R,O: ESCALATE<br/>Agent recommends REFER
        R->>O: {type: escalate, reason: "Cannot resolve<br/>conflicting income signals"}
    end
```

---

## 3. A2A Collaboration Patterns

```mermaid
flowchart TD
    subgraph Pattern1["Pattern: CHALLENGE"]
        P1_1[Risk detects anomaly] --> P1_2[Risk sends FLAG_CONCERN to Affordability]
        P1_2 --> P1_3[Affordability re-evaluates with context]
        P1_3 --> P1_4{Resolved?}
        P1_4 -->|Yes| P1_5[Updated assessment<br/>possibly lower confidence]
        P1_4 -->|No| P1_6[ESCALATE to Orchestrator<br/>→ REFER]
    end

    subgraph Pattern2["Pattern: CONSENSUS CHECK"]
        P2_1[All agents submit assessments] --> P2_2{Score gap < 0.4?}
        P2_2 -->|Yes| P2_3[Proceed to scoring]
        P2_2 -->|No| P2_4[Orchestrator sends REQUEST_REVIEW]
        P2_4 --> P2_5[Agents refine positions]
        P2_5 --> P2_6{Still disagree?}
        P2_6 -->|Yes| P2_7[REFER with both viewpoints]
        P2_6 -->|No| P2_3
    end

    subgraph Pattern3["Pattern: MISSING EVIDENCE"]
        P3_1[Evidence packet has gaps] --> P3_2[Orchestrator notifies affected agents]
        P3_2 --> P3_3[Agents assess with lower confidence]
        P3_3 --> P3_4{Confidence < threshold?}
        P3_4 -->|Yes| P3_5[Force REFER<br/>"Insufficient data for auto-decision"]
        P3_4 -->|No| P3_6[Proceed with flagged assessment]
    end
```

---

## 4. Tools Architecture

```mermaid
graph TD
    subgraph EvidenceTools["Evidence Fetch Tools"]
        T_Bureau["fetch_bureau_data<br/>→ credit_score, exposures,<br/>delinquency, file age"]
        T_Income["fetch_income_data<br/>→ monthly_income, employer,<br/>bank_tx, verification status"]
        T_Exposure["fetch_exposure_data<br/>→ total_exposure, bnpl_count,<br/>obligations, utilization"]
        T_Delinquency["fetch_delinquency_data<br/>→ max_dpd, dpd_counts,<br/>last_dpd_date"]
    end

    subgraph ScoringTools["Scoring Tools"]
        T_Rules["evaluate_rules<br/>→ check conditions against evidence<br/>→ list of triggered rules"]
        T_DTI["compute_dti<br/>→ income / obligations ratio<br/>→ assessment (adequate/marginal/inadequate)"]
        T_Score["compute_weighted_score<br/>→ Σ(weight × agent_score)<br/>→ final score"]
        T_Threshold["apply_thresholds<br/>→ score vs approve/decline thresholds<br/>→ APPROVE / DECLINE / REFER"]
        T_ScoreBand["check_score_band<br/>→ score → band mapping<br/>→ meets minimum?"]
    end

    subgraph PolicyTools["Policy Management Tools"]
        T_LoadPolicy["load_active_policy<br/>→ current policy for segment"]
        T_Simulate["simulate_policy_change<br/>→ run N applicants under new policy<br/>→ impact diff"]
        T_Activate["activate_policy<br/>→ set version as live"]
        T_Rollback["rollback_policy<br/>→ revert to previous version"]
    end

    subgraph ExplanationTools["Explanation Tools"]
        T_Explain["generate_explanation<br/>→ lineage → natural language<br/>→ 3 audience views"]
    end

    subgraph FileTools["Filesystem Tools (Deep Agents built-in)"]
        T_Read["read_file<br/>→ policy YAML, evidence JSON"]
        T_Write["write_file<br/>→ decision records, policy drafts"]
        T_Search["search_files<br/>→ find across evidence/decisions"]
    end
```

---

## 5. Tool Assignment per Agent

```mermaid
graph LR
    subgraph Orchestrator["Orchestrator Tools"]
        OT1[fetch_bureau_data]
        OT2[fetch_income_data]
        OT3[fetch_exposure_data]
        OT4[fetch_delinquency_data]
        OT5[compute_weighted_score]
        OT6[apply_thresholds]
        OT7[load_active_policy]
        OT8[simulate_policy_change]
        OT9[activate_policy]
        OT10[generate_explanation]
        OT11[read_file / write_file]
    end

    subgraph EligTools["Eligibility Tools"]
        ET1[evaluate_rules]
        ET2[check_score_band]
    end

    subgraph AffordTools["Affordability Tools"]
        AT1[fetch_income_data]
        AT2[compute_dti]
    end

    subgraph RiskTools["Risk Tools"]
        RT1[fetch_delinquency_data]
        RT2[fetch_exposure_data]
    end

    Note1[/"Principle: Each agent only<br/>gets tools relevant to its mandate.<br/>Prevents scope bleed."/]
```

---

## 6. MCP (Model Context Protocol) Integration

```mermaid
graph TD
    subgraph MCPServers["MCP Servers (Tool Providers)"]
        MCP_Evidence["Evidence MCP Server<br/>Exposes: bureau, income,<br/>exposure, delinquency tools<br/>as MCP tool definitions"]
        MCP_Policy["Policy MCP Server<br/>Exposes: load, simulate,<br/>activate, rollback tools"]
        MCP_Scoring["Scoring MCP Server<br/>Exposes: rules evaluation,<br/>DTI compute, weighted score"]
    end

    subgraph DeepAgentsRuntime["Deep Agents Runtime"]
        DA[Deep Agents Orchestrator]
        DA -->|tool_call| MCP_Evidence
        DA -->|tool_call| MCP_Policy
        DA -->|tool_call| MCP_Scoring
    end

    subgraph ExternalMCP["External MCP Servers (Production Extension)"]
        MCP_Bureau["Bureau API MCP<br/>(replace mock with real)"]
        MCP_Bank["Bank Data MCP<br/>(real bank statements)"]
        MCP_Fraud["Fraud Detection MCP<br/>(real-time fraud signals)"]
    end

    MCP_Evidence -.->|"swap adapter<br/>mock → real"| MCP_Bureau
    MCP_Evidence -.->|"swap adapter<br/>mock → real"| MCP_Bank
    MCP_Evidence -.->|"swap adapter<br/>mock → real"| MCP_Fraud

    Note2[/"MCP allows swapping mock tools<br/>for real integrations without<br/>changing agent code"/]
```

---

## 7. MCP Tool Definition Schema

```mermaid
graph TD
    subgraph MCPToolSchema["MCP Tool Definition (per tool)"]
        Name["name: fetch_bureau_data"]
        Desc["description: Fetch credit bureau<br/>data for an applicant"]
        Input["inputSchema:<br/>applicant_id: string (required)"]
        Output["Returns: credit_score, score_band,<br/>credit_history_months,<br/>existing_exposures,<br/>delinquency_history,<br/>freshness_days, confidence"]
    end

    subgraph MCPTransport["MCP Transport"]
        STDIO["stdio (local dev)"]
        HTTP["HTTP/SSE (deployed)"]
    end

    subgraph MCPConfig[".mcp.json Configuration"]
        Config["servers:<br/>  evidence-server:<br/>    command: python<br/>    args: [mcp_evidence_server.py]<br/>  policy-server:<br/>    command: python<br/>    args: [mcp_policy_server.py]"]
    end

    MCPToolSchema --> MCPTransport
    MCPTransport --> MCPConfig
```

---

## 8. A2A (Agent-to-Agent) Protocol for Multi-Agent

```mermaid
graph TD
    subgraph A2AProtocol["A2A Protocol Layer"]
        direction TB
        Discovery["Agent Discovery<br/>Each agent exposes:<br/>- name<br/>- description<br/>- capabilities<br/>- tools available"]
        Messaging["Message Passing<br/>Structured messages between agents<br/>with type, content, evidence_refs"]
        TaskDelegation["Task Delegation<br/>Orchestrator delegates subtasks<br/>with isolated context windows"]
        ResultAggregation["Result Aggregation<br/>Orchestrator collects assessments<br/>checks consensus, triggers scoring"]
    end

    subgraph A2AInCredit["A2A in Credit Genie"]
        direction TB
        A2A_Discover["Orchestrator knows:<br/>- Eligibility can gate-check<br/>- Affordability can assess income<br/>- Risk can assess exposure"]
        A2A_Delegate["Orchestrator delegates:<br/>evidence packet + task scope<br/>to each sub-agent"]
        A2A_Communicate["Agents communicate:<br/>Risk → Affordability (concerns)<br/>Affordability → Risk (clarification)"]
        A2A_Collect["Orchestrator collects:<br/>all assessments + messages<br/>feeds to scoring engine"]
    end

    A2AProtocol --> A2AInCredit
```

---

## 9. A2A Message Flow (Detailed)

```mermaid
sequenceDiagram
    participant O as Orchestrator<br/>(A2A Client)
    participant E as Eligibility<br/>(A2A Agent)
    participant A as Affordability<br/>(A2A Agent)
    participant R as Risk<br/>(A2A Agent)

    Note over O,R: DISCOVERY PHASE
    O->>E: GET /agent-card → capabilities
    O->>A: GET /agent-card → capabilities
    O->>R: GET /agent-card → capabilities

    Note over O,R: TASK DELEGATION PHASE
    O->>E: POST /task {evidence_packet, scope: "eligibility"}
    E-->>O: {status: complete, result: PASS}

    par Parallel Delegation
        O->>A: POST /task {evidence_packet, scope: "affordability"}
        O->>R: POST /task {evidence_packet, scope: "risk"}
    end

    Note over R,A: INTER-AGENT COMMUNICATION
    R->>A: POST /message {type: flag_concern,<br/>content: "irregular deposits detected"}
    A-->>A: Re-evaluate
    A->>R: POST /message {type: provide_context,<br/>content: "deposits are freelance income"}

    Note over O,R: RESULT COLLECTION
    A-->>O: {status: complete, result: {assessment: "adequate", confidence: 0.82}}
    R-->>O: {status: complete, result: {risk_level: "moderate", confidence: 0.78}}

    Note over O: CONSENSUS + SCORING
    O->>O: Check agreement → aligned
    O->>O: compute_weighted_score → 0.72
    O->>O: apply_thresholds → APPROVE
```

---

## 10. Deep Agents Deploy — Production Architecture

```mermaid
graph TD
    subgraph DeepAgentsDeploy["Deep Agents Deploy"]
        direction TB
        Endpoints["Exposed Endpoints:<br/>- MCP endpoint (tool calls)<br/>- A2A endpoint (agent-to-agent)<br/>- Human-in-the-loop endpoint<br/>- SSE streaming endpoint"]
        Runtime["LangGraph Runtime<br/>- Streaming<br/>- Persistence<br/>- Checkpointing<br/>- Resume on crash"]
        Memory["Persistent Memory<br/>- PostgreSQL (production)<br/>- Filesystem (hackathon)<br/>- Cross-session recall"]
    end

    subgraph Observability["LangSmith Observability"]
        Traces["Trace every decision"]
        Latency["Latency per stage"]
        TokenUsage["Token usage per agent"]
        Evaluation["Decision quality eval"]
    end

    subgraph Clients["Clients"]
        WebUI["Web Dashboard (SSE)"]
        API_Client["API Client (REST)"]
        OtherAgent["Other Agents (A2A)"]
        MCPClient["MCP Client (tools)"]
    end

    Clients --> DeepAgentsDeploy
    DeepAgentsDeploy --> Observability
```

---

## 11. Skills Structure

```mermaid
graph TD
    subgraph SkillsDir["skills/ directory"]
        subgraph CreditPolicy["credit-policy/"]
            CP_Elig["eligibility/<br/>- Min score bands per segment<br/>- File age requirements<br/>- Blacklist rules"]
            CP_Afford["affordability/<br/>- DTI thresholds<br/>- Income stability criteria<br/>- Bank statement patterns"]
            CP_Risk["risk/<br/>- DPD severity levels<br/>- Exposure limits<br/>- BNPL stacking rules"]
        end

        subgraph EvidenceRules["evidence-rules/"]
            ER_Fresh["freshness-limits/<br/>- Bureau: max 7 days<br/>- Income: max 30 days<br/>- Exposure: max 1 day"]
            ER_Conf["confidence-mapping/<br/>- verified = 1.0<br/>- declared = 0.7<br/>- inferred = 0.4<br/>- missing = 0.0"]
            ER_Missing["missing-data-handling/<br/>- NEVER treat as zero<br/>- Flag for REFER if critical<br/>- Lower confidence if optional"]
        end

        subgraph Explanation["explanation/"]
            EX_Templates["templates/<br/>- Reason code → customer text<br/>- Reason code → reviewer text"]
            EX_Codes["reason-codes/<br/>- SEVERE_DELINQUENCY<br/>- UNAFFORDABLE<br/>- THIN_FILE<br/>- CONFLICTING_SIGNALS"]
            EX_Format["audience-formatting/<br/>- Customer: empathetic, actionable<br/>- Reviewer: detailed, factual<br/>- Audit: complete, machine-readable"]
        end

        subgraph FraudSignals["fraud-signals/"]
            FS_Patterns["patterns/<br/>- Income inconsistency<br/>- Application velocity<br/>- Synthetic identity markers"]
        end
    end

    Note3[/"Skills are loaded ON DEMAND<br/>by agents when needed.<br/>Sub-agents get only<br/>their assigned skills."/]
```

---

## 12. Complete System — All Components Connected

```mermaid
graph TB
    subgraph External["External Interfaces"]
        WebUI[Web Dashboard]
        A2A_Ext[Other A2A Agents]
        MCP_Ext[MCP Clients]
        HITL[Human Reviewers]
    end

    subgraph API["API Layer"]
        FastAPI[FastAPI<br/>REST + SSE]
        A2A_Endpoint[A2A Endpoint]
        MCP_Endpoint[MCP Endpoint]
    end

    subgraph Core["Deep Agents Core"]
        Orchestrator[Orchestrator Agent<br/>Planning + Context + Delegation]
        
        subgraph Agents["Sub-Agents (A2A)"]
            Elig[Eligibility<br/>Rules-only<br/>Gate check]
            Afford[Affordability<br/>LLM-powered<br/>Income analysis]
            Risk_Agent[Risk<br/>Hybrid<br/>Challenger role]
        end
        
        subgraph ToolsLayer["Tools (MCP)"]
            ET[Evidence Tools]
            ST[Scoring Tools]
            PT[Policy Tools]
            ExT[Explanation Tools]
        end

        SkillsLayer[Skills<br/>Policy knowledge<br/>Evidence rules<br/>Fraud patterns]
    end

    subgraph Storage["Filesystem Backend"]
        PolicyYAML[Policy YAML<br/>Versioned configs]
        EvidenceJSON[Evidence JSON<br/>Mock fixtures]
        DecisionJSON[Decision Ledger<br/>Immutable records]
        AgentMemory[AGENTS.md<br/>Persistent memory]
    end

    subgraph Infra["Infrastructure"]
        LangGraph[LangGraph Runtime<br/>Stream + Persist + Checkpoint]
        LangSmith[LangSmith<br/>Traces + Eval]
        Claude[Claude API<br/>Structured output]
    end

    WebUI --> FastAPI
    A2A_Ext --> A2A_Endpoint
    MCP_Ext --> MCP_Endpoint
    HITL --> FastAPI

    FastAPI --> Orchestrator
    A2A_Endpoint --> Orchestrator
    MCP_Endpoint --> ToolsLayer

    Orchestrator --> Agents
    Agents --> ToolsLayer
    Orchestrator --> SkillsLayer
    ToolsLayer --> Storage

    Orchestrator --> LangGraph
    LangGraph --> LangSmith
    Agents --> Claude
```
