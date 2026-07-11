import { useEffect, useState } from "react";
import { fetchDecisions } from "../api/client";
import { DecisionCard } from "../components/DecisionCard";
import { OutcomeBadge } from "../components/OutcomeBadge";
import type { DecisionRecord } from "../types";

export function Ledger() {
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [selected, setSelected] = useState<DecisionRecord | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchDecisions()
      .then((list) => setDecisions([...list].reverse())) // newest first
      .finally(() => setLoaded(true));
  }, []);

  if (loaded && decisions.length === 0) {
    return <p className="text-[13px] text-ink-muted">No decisions recorded yet. Run a decision from the Dashboard — every outcome is written to the immutable ledger.</p>;
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="overflow-x-auto rounded-sm border border-border bg-surface">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-border bg-surface-2 font-mono text-[10px] uppercase tracking-wide text-ink-muted">
              <th className="px-2.5 py-1.5 text-left">Decision</th>
              <th className="px-2.5 py-1.5 text-left">Applicant</th>
              <th className="px-2.5 py-1.5 text-left">Product</th>
              <th className="px-2.5 py-1.5 text-left">Outcome</th>
              <th className="px-2.5 py-1.5 text-left">Reason</th>
              <th className="px-2.5 py-1.5 text-left">Policy</th>
              <th className="px-2.5 py-1.5 text-right">Latency</th>
              <th className="px-2.5 py-1.5 text-left">At (UTC)</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d) => (
              <tr
                key={d.decision_id}
                onClick={() => setSelected(selected?.decision_id === d.decision_id ? null : d)}
                className={`cursor-pointer border-b border-border last:border-0 hover:bg-surface-2 ${
                  selected?.decision_id === d.decision_id ? "bg-accent-soft" : ""
                }`}
              >
                <td className="px-2.5 py-1.5 font-mono text-[11px]">{d.decision_id}</td>
                <td className="px-2.5 py-1.5">{d.applicant_id}</td>
                <td className="px-2.5 py-1.5 font-mono text-[11px]">{d.product}</td>
                <td className="px-2.5 py-1.5"><OutcomeBadge outcome={d.outcome} size="sm" /></td>
                <td className="px-2.5 py-1.5 font-mono text-[11px] text-ink-muted">{d.reason_code}</td>
                <td className="px-2.5 py-1.5 font-mono text-[11px] text-ink-muted">
                  v{d.lineage.policy_version} · {d.lineage.policy_hash}
                </td>
                <td className="px-2.5 py-1.5 text-right font-mono text-[11px] tabular-nums">{d.latency_ms?.toFixed(0)}ms</td>
                <td className="px-2.5 py-1.5 font-mono text-[11px] text-ink-muted">{d.created_at.slice(0, 19).replace("T", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <section>
          <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-muted">Decision lineage — {selected.decision_id}</h2>
          <DecisionCard record={selected} />
        </section>
      )}
    </div>
  );
}
