export type Outcome = "APPROVE" | "DECLINE" | "REFER";
export type Product = "personal_loan" | "bnpl";

export interface Applicant {
  applicant_id: string;
  display_name: string;
  products: Product[];
  persona_note: string;
  expected_outcome: string;
}

export interface Factor {
  name: string;
  value: string;
  evidence_ref: string;
  impact: "positive" | "negative" | "neutral";
}

export interface AgentMessage {
  from_agent: string;
  to_agent: string | null;
  message_type: "assessment" | "flag_concern" | "request_review" | "provide_context" | "escalate";
  content: string;
  evidence_refs: string[];
  timestamp: string;
}

export interface DecisionLineage {
  applicant_id: string;
  product: Product;
  policy_version: string;
  policy_hash: string;
  eligibility_result: { result: "PASS" | "FAIL"; reasons: string[]; score_band: string | null };
  hard_rules_triggered: { id: string; condition: string; reason_code: string }[];
  affordability_assessment: Record<string, unknown> | null;
  risk_assessment: Record<string, unknown> | null;
  consensus: Record<string, unknown> | null;
  component_scores: Record<string, number> | null;
  final_score: number | null;
  thresholds: Record<string, number> | null;
  decisive_factors: string[];
  agent_messages: AgentMessage[];
  evidence_snapshot: Record<string, unknown>;
  timing_ms: Record<string, number>;
  degradations: string[];
}

export interface DecisionRecord {
  decision_id: string;
  applicant_id: string;
  product: Product;
  outcome: Outcome;
  reason_code: string;
  lineage: DecisionLineage;
  explanation: { customer: string; reviewer: string };
  created_at: string;
  latency_ms: number | null;
}

export type StageName = "ingest" | "reason" | "score" | "explain";

export interface PipelineStage {
  stage: StageName;
  status: "pending" | "active" | "done";
  timing_ms?: number;
  outcome?: Outcome;
}

export interface PolicySegment {
  mode: string;
  time_budget_ms: number;
  scoring: { weights: Record<string, number>; thresholds: Record<string, number> };
  features: Record<string, boolean>;
  eligibility: { min_score_band: string; min_credit_history_months: number };
  affordability: { dti_decline_ceiling: number };
  risk: { max_bnpl_stacking: number; max_utilization: number };
}

export interface Policy {
  hash: string;
  version: string;
  effective_date: string | null;
  status: string;
  approved_by: string | null;
  change_reason: string;
  segments: Record<Product, PolicySegment>;
  hard_rules: { id: string; condition: string; action: Outcome; reason_code: string; applies_to: Product[] }[];
}

export interface PolicyDraft {
  filename: string;
  version: string;
  status: string;
  change_reason: string;
  drafted_by: string;
}

export interface SimulateResultRow {
  applicant_id: string;
  old: { outcome: Outcome; reason_code: string; final_score?: number };
  new: { outcome: Outcome; reason_code: string; final_score?: number };
  changed: boolean;
}

export interface SimulateResult {
  draft_version: string;
  active_version: string;
  total: number;
  changed: number;
  results: SimulateResultRow[];
}
