import { useState } from "react";
import type { DecisionRecord } from "../types";
import { OutcomeBadge } from "./OutcomeBadge";

const COMPONENT_LABEL: Record<string, string> = { eligibility: "Eligibility", affordability: "Affordability", risk: "Risk" };

function ScoreBreakdown({ record }: { record: DecisionRecord }) {
  const scores = record.lineage.component_scores;
  if (!scores) return null;
  return (
    <div className="flex flex-col gap-2">
      {Object.entries(scores).map(([key, value]) => (
        <div key={key} className="flex items-center gap-2">
          <span className="w-24 shrink-0 font-mono text-[11px] text-ink-muted">{COMPONENT_LABEL[key] ?? key}</span>
          <div className="h-2 flex-1 rounded-full bg-surface-2">
            <div className="h-2 rounded-full bg-accent" style={{ width: `${Math.round(value * 100)}%` }} />
          </div>
          <span className="w-10 shrink-0 text-right font-mono text-[11px] tabular-nums">{value.toFixed(2)}</span>
        </div>
      ))}
      {record.lineage.final_score !== null && (
        <div className="mt-1 flex items-center justify-between border-t border-border pt-2 font-mono text-[12px]">
          <span className="text-ink-muted">final_score</span>
          <span className="font-semibold tabular-nums">{record.lineage.final_score?.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}

function BnplReasoning({ record }: { record: DecisionRecord }) {
  const assessment = record.lineage.bnpl_reasoning_assessment;
  if (record.product !== "bnpl") return null;

  return (
    <div className="mt-4 rounded-sm border border-border bg-surface-2 p-3">
      <div className="flex items-center justify-between font-mono text-[11px] uppercase tracking-wide">
        <span className="font-semibold text-accent">BNPL reasoning agent</span>
        <span className="text-ink-muted">
          {record.lineage.agent_reasoning_status}
          {assessment ? ` · confidence ${assessment.confidence.toFixed(2)}` : ""}
        </span>
      </div>
      {assessment && (
        <>
          <p className="mt-2 text-[13px] leading-relaxed">{assessment.reasoning}</p>
          <div className="mt-2 flex flex-wrap gap-1.5 font-mono text-[10px] text-ink-muted">
            <span className="rounded-sm bg-surface px-1.5 py-0.5">affordability: {assessment.affordability}</span>
            <span className="rounded-sm bg-surface px-1.5 py-0.5">risk: {assessment.risk}</span>
            {assessment.evidence_refs.map((evidenceRef) => (
              <span key={evidenceRef} className="rounded-sm bg-surface px-1.5 py-0.5">
                cites {evidenceRef}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

type Tab = "customer" | "reviewer" | "audit";

const CUSTOMER_PRESENTATION = {
  APPROVE: {
    title: "Application approved",
    symbol: "✓",
    container: "border-approve bg-approve-soft",
    symbolStyle: "bg-approve text-white",
  },
  DECLINE: {
    title: "Application not approved",
    symbol: "×",
    container: "border-decline bg-decline-soft",
    symbolStyle: "bg-decline text-white",
  },
  REFER: {
    title: "Application needs review",
    symbol: "…",
    container: "border-refer bg-refer-soft",
    symbolStyle: "bg-refer text-white",
  },
} as const;

function CustomerExplanation({ record }: { record: DecisionRecord }) {
  const presentation = CUSTOMER_PRESENTATION[record.outcome];

  return (
    <section
      aria-label="Customer-facing decision explanation"
      className={`min-w-0 rounded-sm border-l-4 p-4 ${presentation.container}`}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${presentation.symbolStyle}`}
        >
          {presentation.symbol}
        </span>
        <div className="min-w-0">
          <p className="font-semibold text-ink">{presentation.title}</p>
          <p className="mt-1 whitespace-pre-line break-words text-pretty text-[14px] leading-6 text-ink">
            {record.explanation.customer}
          </p>
        </div>
      </div>
    </section>
  );
}

export function DecisionCard({ record }: { record: DecisionRecord }) {
  const [tab, setTab] = useState<Tab>("customer");

  return (
    <div className="min-w-0 max-w-full overflow-hidden rounded-sm border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <OutcomeBadge outcome={record.outcome} />
          <span className="font-mono text-xs text-ink-muted">{record.reason_code}</span>
        </div>
        <span className="font-mono text-[11px] text-ink-muted">{record.decision_id} &middot; {record.latency_ms?.toFixed(0)}ms</span>
      </div>

      {record.lineage.decisive_factors.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1">
          {record.lineage.decisive_factors.map((f, i) => (
            <li key={i} className="break-words text-[13px] text-ink-muted">
              &bull; {f}
            </li>
          ))}
        </ul>
      )}

      {record.lineage.component_scores && (
        <div className="mt-4">
          <ScoreBreakdown record={record} />
        </div>
      )}

      <BnplReasoning record={record} />

      {record.lineage.degradations.length > 0 && (
        <div className="mt-3 rounded-sm border border-dashed border-border px-2.5 py-1.5 text-[11px] text-ink-muted">
          Degraded: {record.lineage.degradations.join("; ")}
        </div>
      )}

      <div className="mt-4 flex gap-1 border-b border-border">
        {(["customer", "reviewer", "audit"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-wide ${
              tab === t ? "border-b-2 border-accent text-accent" : "text-ink-muted hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-2 min-w-0 max-w-full text-[13px] leading-relaxed">
        {tab === "customer" && <CustomerExplanation record={record} />}
        {tab === "reviewer" && (
          <div className="min-w-0 rounded-sm border border-border bg-surface-2 p-3.5">
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-ink-muted">Reviewer rationale</p>
            <p className="whitespace-pre-line break-words text-[13px] leading-5 text-ink">{record.explanation.reviewer}</p>
          </div>
        )}
        {tab === "audit" && (
          <pre className="block max-h-72 w-full max-w-full overflow-x-auto overflow-y-auto rounded-sm bg-surface-2 p-2.5 font-mono text-[11px] leading-snug">
            {JSON.stringify(record.lineage, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
