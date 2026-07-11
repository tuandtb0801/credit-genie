import type { ApplicantEvidence } from "../types";

function fmtMoney(v: number | null | undefined): string {
  return v == null ? "—" : `$${v.toLocaleString()}`;
}

function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function Signal({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" | "warn" }) {
  const toneClass = tone === "bad" ? "text-decline" : tone === "warn" ? "text-refer" : tone === "good" ? "text-approve" : "";
  return (
    <div className="flex flex-col gap-0.5 rounded-sm border border-border bg-surface px-2.5 py-1.5">
      <span className="font-mono text-[9.5px] uppercase tracking-wide text-ink-muted">{label}</span>
      <span className={`font-mono text-[12.5px] font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}

export function EvidencePanel({ evidence }: { evidence: ApplicantEvidence }) {
  const s = evidence.signals;
  const verified = evidence.income_verification_status === "verified";
  const irregular = evidence.deposit_pattern.pattern === "irregular";

  return (
    <div className="rounded-sm border border-border bg-surface-2 p-3">
      <div className="grid grid-cols-3 gap-1.5 md:grid-cols-5">
        <Signal label="Score band" value={`${s.score_band ?? "?"} (${s.credit_score ?? "—"})`} tone={s.score_band === "poor" ? "bad" : undefined} />
        <Signal label="History" value={`${s.credit_history_months ?? "—"} mo`} tone={(s.credit_history_months ?? 99) < 6 ? "warn" : undefined} />
        <Signal label="Income /mo" value={fmtMoney(s.monthly_income)} />
        <Signal label="Obligations /mo" value={fmtMoney(s.monthly_obligations)} />
        <Signal label="DTI" value={fmtPct(s.dti_ratio)} tone={s.dti_ratio > 0.4 ? "bad" : s.dti_ratio > 0.3 ? "warn" : "good"} />
        <Signal label="Max DPD" value={`${s.max_dpd} days`} tone={s.max_dpd >= 90 ? "bad" : s.max_dpd > 0 ? "warn" : "good"} />
        <Signal label="BNPL plans" value={`${s.bnpl_active_count} active`} tone={s.bnpl_active_count > 3 ? "bad" : undefined} />
        <Signal label="Utilization" value={fmtPct(s.utilization_ratio)} tone={s.utilization_ratio > 0.8 ? "bad" : s.utilization_ratio > 0.6 ? "warn" : undefined} />
        <Signal label="Exposure" value={fmtMoney(s.total_exposure)} />
        <Signal
          label="Income verif."
          value={`${evidence.income_verification_status} · ${evidence.employment_type.replace("_", "-")}`}
          tone={verified ? "good" : "warn"}
        />
      </div>
      <p className={`mt-2 text-[11.5px] leading-snug ${irregular ? "text-refer" : "text-ink-muted"}`}>
        <span className="font-mono text-[9.5px] uppercase tracking-wide">Deposits: {evidence.deposit_pattern.pattern}</span>{" "}
        — {evidence.deposit_pattern.note}
        {evidence.bnpl_providers.length > 1 && <span> Providers: {evidence.bnpl_providers.join(", ")}.</span>}
      </p>
    </div>
  );
}
