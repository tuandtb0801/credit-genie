import type { PipelineStage } from "../types";

const LABELS: Record<string, string> = {
  ingest: "Evidence Ingest",
  reason: "Multi-Agent Reasoning",
  score: "Scoring",
  explain: "Explanation",
};

export function PipelineViz({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="flex items-stretch gap-2">
      {stages.map((s, i) => (
        <div key={s.stage} className="flex flex-1 items-center gap-2">
          <div
            className={`flex-1 rounded-sm border px-3 py-2.5 transition-colors ${
              s.status === "done"
                ? "border-accent/40 bg-accent-soft"
                : s.status === "active"
                  ? "border-accent bg-accent-soft animate-pulse"
                  : "border-border bg-surface-2"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">Stage {i + 1}</span>
              {s.status === "done" && s.timing_ms !== undefined && (
                <span className="font-mono text-[10px] text-ink-muted">{s.timing_ms.toFixed(0)}ms</span>
              )}
              {s.status === "active" && <span className="h-1.5 w-1.5 animate-ping rounded-full bg-accent" />}
            </div>
            <div className="mt-0.5 text-[13px] font-semibold">{LABELS[s.stage] ?? s.stage}</div>
          </div>
          {i < stages.length - 1 && <span className="text-border">&rarr;</span>}
        </div>
      ))}
    </div>
  );
}
