import { useEffect, useState } from "react";
import { activatePolicy, backtestPolicy, draftRule, fetchActivePolicy, fetchDrafts, rollbackPolicy, simulatePolicy } from "../api/client";
import type { DraftRuleResult } from "../api/client";
import { BacktestPanel } from "../components/BacktestPanel";
import { OutcomeBadge } from "../components/OutcomeBadge";
import type { BacktestResult, Policy, PolicyDraft, Product, SimulateResult } from "../types";

function RuleDrafter({ onDrafted }: { onDrafted: (filename: string | null) => Promise<void> | void }) {
  const [intent, setIntent] = useState("");
  const [requestedBy, setRequestedBy] = useState("risk-analyst@credit-genie");
  const [result, setResult] = useState<DraftRuleResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    if (!intent.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await draftRule(intent.trim(), requestedBy);
      setResult(r);
      if (r.created) await onDrafted(r.filename ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rule drafting failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 rounded-sm border border-border bg-surface p-4">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Draft a rule from plain English</h3>
      <textarea
        value={intent}
        onChange={(e) => setIntent(e.target.value)}
        rows={2}
        placeholder='e.g. "Refer anyone with under 12 months of credit history and more than 2 active BNPL plans"'
        className="mt-2 w-full rounded-sm border border-border bg-surface px-2 py-1.5 text-[12px]"
      />
      <div className="mt-2 flex items-center gap-2">
        <input
          value={requestedBy}
          onChange={(e) => setRequestedBy(e.target.value)}
          className="flex-1 rounded-sm border border-border bg-surface px-2 py-1.5 font-mono text-[11px]"
          placeholder="analyst identity"
        />
        <button
          onClick={run}
          disabled={busy || !intent.trim()}
          className="rounded-sm bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-white disabled:opacity-40"
        >
          {busy ? "Drafting…" : "Draft rule"}
        </button>
      </div>
      <p className="mt-1 text-[10.5px] text-ink-muted">
        The agent only proposes: the rule lands as a draft that still needs simulate, back-test, and approver sign-off.
      </p>

      {error && <p className="mt-2 text-[12px] text-decline">{error}</p>}
      {result && !result.created && result.refused && (
        <div className="mt-2 rounded-sm border border-dashed border-refer bg-refer-soft px-2.5 py-1.5 text-[11.5px] text-refer">
          Agent refused to draft this rule: {result.refusal_reason}
        </div>
      )}
      {result && !result.created && !result.refused && (
        <div className="mt-2 rounded-sm border border-dashed border-decline px-2.5 py-1.5 text-[11.5px] text-decline">
          Guardrails rejected the drafted rule: {result.errors.join("; ")}
        </div>
      )}
      {result?.created && result.rule && (
        <div className="mt-2 rounded-sm border border-border bg-surface-2 px-2.5 py-2">
          <p className="text-[12px]">
            <span className="font-mono font-semibold">{result.rule.id}</span> — {result.rule.description}
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-ink-muted">
            {result.rule.condition} &rarr; {result.rule.action} ({result.rule.reason_code}) · {result.rule.applies_to.join(", ")}
          </p>
          {result.impact && (
            <p className="mt-1 font-mono text-[10.5px] text-ink-muted">
              Historic-book impact:{" "}
              {Object.entries(result.impact)
                .map(([p, rate]) => `${p} ${(rate * 100).toFixed(1)}%`)
                .join(" · ")}
            </p>
          )}
          {result.warnings?.map((w) => (
            <p key={w} className="mt-1 rounded-sm border border-dashed border-refer px-2 py-1 text-[11px] text-refer">
              ⚠ {w}
            </p>
          ))}
          <p className="mt-1 font-mono text-[10.5px] text-ink-muted">Draft created: {result.filename} (v{result.version})</p>
        </div>
      )}
    </div>
  );
}

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
            <li key={r.id} className="text-[11px]">
              {r.description && (
                <p className="text-[12px] text-ink">
                  <span className="font-mono font-semibold">{r.id}</span> — {r.description}
                </p>
              )}
              <p className="font-mono text-ink-muted">
                {!r.description && <span className="font-semibold">{r.id}: </span>}
                {r.condition} &rarr; {r.action} ({r.reason_code})
              </p>
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
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [approvedBy, setApprovedBy] = useState("risk-approver@credit-genie");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh(selectFilename?: string | null) {
    setActive(await fetchActivePolicy());
    const d = await fetchDrafts();
    setDrafts(d);
    setSelectedDraft(selectFilename && d.some((x) => x.filename === selectFilename) ? selectFilename : d[0]?.filename ?? null);
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

  async function runBacktest() {
    if (!selectedDraft) return;
    setBusy(true);
    setMessage(null);
    try {
      setBacktestResult(await backtestPolicy(selectedDraft, product));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Back-test failed.");
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
      setBacktestResult(null);
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
      setBacktestResult(null);
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
                  v{d.version} — {d.filename}{d.stale ? " (STALE)" : ""}
                </option>
              ))}
            </select>
            {selectedDraft && <p className="mt-2 text-[12px] text-ink-muted">{drafts.find((d) => d.filename === selectedDraft)?.change_reason}</p>}
            {drafts.find((d) => d.filename === selectedDraft)?.stale && (
              <p className="mt-2 rounded-sm border border-dashed border-refer bg-refer-soft px-2 py-1 text-[11.5px] text-refer">
                Stale draft: it forked from an older active policy, so activating it would revert rules added since. Redraft from the current policy instead.
              </p>
            )}

            <div className="mt-3 flex items-center gap-1 rounded-sm border border-border bg-surface-2 p-1">
              {(["personal_loan", "bnpl"] as Product[]).map((p) => (
                <button key={p} onClick={() => setProduct(p)} className={`flex-1 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-wide ${product === p ? "bg-surface text-accent shadow-sm" : "text-ink-muted"}`}>
                  {p === "personal_loan" ? "Personal Loan" : "BNPL"}
                </button>
              ))}
            </div>

            <div className="mt-3 flex gap-2">
              <button onClick={runSimulate} disabled={busy} className="flex-1 rounded-sm border border-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-accent hover:bg-accent-soft disabled:opacity-40">
                Simulate impact
              </button>
              <button onClick={runBacktest} disabled={busy} className="flex-1 rounded-sm border border-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-accent hover:bg-accent-soft disabled:opacity-40">
                Back-test on history
              </button>
            </div>

            {simResult && <SimulateTable result={simResult} />}
            {backtestResult && <BacktestPanel result={backtestResult} />}

            <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
              <input value={approvedBy} onChange={(e) => setApprovedBy(e.target.value)} className="flex-1 rounded-sm border border-border bg-surface px-2 py-1.5 font-mono text-[11px]" placeholder="approver identity" />
              <button
                onClick={runActivate}
                disabled={busy || drafts.find((d) => d.filename === selectedDraft)?.stale}
                className="rounded-sm bg-accent px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-white disabled:opacity-40"
              >
                Activate
              </button>
            </div>
            <p className="mt-1 text-[10.5px] text-ink-muted">Editor and approver are separate identities by design — see docs/decision-modes-and-controls.md.</p>
          </div>
        )}
        {message && <p className="mt-2 text-[12px] text-ink-muted">{message}</p>}

        <RuleDrafter onDrafted={(filename) => refresh(filename)} />
      </div>
    </div>
  );
}
