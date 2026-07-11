import { useEffect, useState } from "react";
import { activatePolicy, fetchActivePolicy, fetchDrafts, rollbackPolicy, simulatePolicy } from "../api/client";
import { OutcomeBadge } from "../components/OutcomeBadge";
import type { Policy, PolicyDraft, Product, SimulateResult } from "../types";

function PolicySummary({ policy }: { policy: Policy }) {
  return (
    <div className="rounded-sm border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-semibold">v{policy.version}</span>
        <span className="rounded-sm bg-approve-soft px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-approve">{policy.status}</span>
      </div>
      <p className="mt-1 text-[12px] text-ink-muted">{policy.change_reason}</p>
      <dl className="mt-3 flex flex-col gap-1 font-mono text-[11px]">
        <div className="flex justify-between"><dt className="text-ink-muted">effective_date</dt><dd>{policy.effective_date ?? "—"}</dd></div>
        <div className="flex justify-between"><dt className="text-ink-muted">approved_by</dt><dd>{policy.approved_by ?? "—"}</dd></div>
        <div className="flex justify-between"><dt className="text-ink-muted">hash</dt><dd>{policy.hash}</dd></div>
      </dl>

      {(Object.entries(policy.segments) as [Product, Policy["segments"][Product]][]).map(([product, segment]) => (
        <div key={product} className="mt-3 border-t border-border pt-3">
          <div className="font-mono text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{product}</div>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono text-[11px]">
            <span>approve &ge; {segment.scoring.thresholds.approve}</span>
            <span>decline &le; {segment.scoring.thresholds.decline}</span>
            <span>dti_ceiling {segment.affordability.dti_decline_ceiling}</span>
            <span>llm {segment.features.llm_reasoning ? "on" : "off"}</span>
          </div>
        </div>
      ))}

      <div className="mt-3 border-t border-border pt-3">
        <div className="font-mono text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Hard Rules</div>
        <ul className="mt-1 flex flex-col gap-1">
          {policy.hard_rules.map((r) => (
            <li key={r.id} className="font-mono text-[11px] text-ink-muted">
              {r.id}: {r.condition} &rarr; {r.action} ({r.reason_code})
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function SimulateTable({ result }: { result: SimulateResult }) {
  return (
    <div className="mt-3 overflow-x-auto rounded-sm border border-border">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-border bg-surface-2 font-mono text-[10px] uppercase tracking-wide text-ink-muted">
            <th className="px-2.5 py-1.5 text-left">Applicant</th>
            <th className="px-2.5 py-1.5 text-left">v{result.active_version}</th>
            <th className="px-2.5 py-1.5 text-left">v{result.draft_version}</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <tr key={row.applicant_id} className={`border-b border-border last:border-0 ${row.changed ? "bg-accent-soft" : ""}`}>
              <td className="px-2.5 py-1.5">{row.applicant_id}</td>
              <td className="px-2.5 py-1.5"><OutcomeBadge outcome={row.old.outcome} size="sm" /></td>
              <td className="px-2.5 py-1.5"><OutcomeBadge outcome={row.new.outcome} size="sm" /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-border px-2.5 py-1.5 font-mono text-[11px] text-ink-muted">
        {result.changed} of {result.total} decisions would change.
      </p>
    </div>
  );
}

export function PolicyEditor() {
  const [active, setActive] = useState<Policy | null>(null);
  const [drafts, setDrafts] = useState<PolicyDraft[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<string | null>(null);
  const [product, setProduct] = useState<Product>("personal_loan");
  const [simResult, setSimResult] = useState<SimulateResult | null>(null);
  const [approvedBy, setApprovedBy] = useState("risk-approver@credit-genie");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setActive(await fetchActivePolicy());
    const d = await fetchDrafts();
    setDrafts(d);
    setSelectedDraft(d[0]?.filename ?? null);
  }

  useEffect(() => {
    refresh();
  }, []);

  async function runSimulate() {
    if (!selectedDraft) return;
    setBusy(true);
    setMessage(null);
    try {
      setSimResult(await simulatePolicy(selectedDraft, product));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Simulation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runActivate() {
    if (!selectedDraft) return;
    setBusy(true);
    setMessage(null);
    try {
      await activatePolicy(selectedDraft, approvedBy);
      setMessage(`Activated. New decisions now use the updated policy.`);
      setSimResult(null);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Activation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runRollback() {
    setBusy(true);
    setMessage(null);
    try {
      await rollbackPolicy();
      setMessage("Rolled back to the previous policy version.");
      setSimResult(null);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Rollback failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-muted">Active Policy</h2>
        {active && <PolicySummary policy={active} />}
        <button onClick={runRollback} disabled={busy} className="mt-2 w-full rounded-sm border border-border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-ink-muted hover:bg-surface-2 disabled:opacity-40">
          Rollback to previous version
        </button>
      </div>

      <div>
        <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-muted">Draft</h2>
        {drafts.length === 0 ? (
          <p className="text-[12px] text-ink-muted">No drafts pending.</p>
        ) : (
          <div className="rounded-sm border border-border bg-surface p-4">
            <select value={selectedDraft ?? ""} onChange={(e) => setSelectedDraft(e.target.value)} className="w-full rounded-sm border border-border bg-surface px-2 py-1.5 font-mono text-[12px]">
              {drafts.map((d) => (
                <option key={d.filename} value={d.filename}>
                  v{d.version} — {d.filename}
                </option>
              ))}
            </select>
            {selectedDraft && <p className="mt-2 text-[12px] text-ink-muted">{drafts.find((d) => d.filename === selectedDraft)?.change_reason}</p>}

            <div className="mt-3 flex items-center gap-1 rounded-sm border border-border bg-surface-2 p-1">
              {(["personal_loan", "bnpl"] as Product[]).map((p) => (
                <button key={p} onClick={() => setProduct(p)} className={`flex-1 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-wide ${product === p ? "bg-surface text-accent shadow-sm" : "text-ink-muted"}`}>
                  {p === "personal_loan" ? "Personal Loan" : "BNPL"}
                </button>
              ))}
            </div>

            <button onClick={runSimulate} disabled={busy} className="mt-3 w-full rounded-sm border border-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-accent hover:bg-accent-soft disabled:opacity-40">
              Simulate impact
            </button>

            {simResult && <SimulateTable result={simResult} />}

            <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
              <input value={approvedBy} onChange={(e) => setApprovedBy(e.target.value)} className="flex-1 rounded-sm border border-border bg-surface px-2 py-1.5 font-mono text-[11px]" placeholder="approver identity" />
              <button onClick={runActivate} disabled={busy} className="rounded-sm bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-white disabled:opacity-40">
                Activate
              </button>
            </div>
            <p className="mt-1 text-[10.5px] text-ink-muted">Editor and approver are separate identities by design — see docs/decision-modes-and-controls.md.</p>
          </div>
        )}
        {message && <p className="mt-2 text-[12px] text-ink-muted">{message}</p>}
      </div>
    </div>
  );
}
