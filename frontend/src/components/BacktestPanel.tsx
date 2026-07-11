import type { BacktestResult } from "../types";

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}

function money(v: number | null | undefined): string {
  return v == null ? "—" : `$${Math.round(v).toLocaleString()}`;
}

/** Delta where a rise is bad (bad-rate, expected loss). */
function DeltaBad({ value, fmt }: { value: number | null; fmt: (v: number) => string }) {
  if (value == null) return <span className="text-ink-muted">—</span>;
  const worse = value > 0;
  return (
    <span className={`font-semibold ${worse ? "text-decline" : "text-approve"}`}>
      {value > 0 ? "+" : ""}{fmt(value)}
    </span>
  );
}

export function BacktestPanel({ result }: { result: BacktestResult }) {
  const rows: { label: string; active: string; draft: string; delta: React.ReactNode }[] = [
    {
      label: "Approval rate",
      active: pct(result.active.approval_rate),
      draft: pct(result.draft.approval_rate),
      delta: (
        <span className="font-semibold text-accent">
          {result.deltas.approval_rate != null && result.deltas.approval_rate > 0 ? "+" : ""}
          {pct(result.deltas.approval_rate)}
        </span>
      ),
    },
    {
      label: "Bad rate among approved",
      active: pct(result.active.bad_rate_among_approved),
      draft: pct(result.draft.bad_rate_among_approved),
      delta: <DeltaBad value={result.deltas.bad_rate_among_approved} fmt={(v) => `${(v * 100).toFixed(1)}pt`} />,
    },
    {
      label: `Expected loss (LGD ${result.book.lgd})`,
      active: money(result.active.expected_loss),
      draft: money(result.draft.expected_loss),
      delta: <DeltaBad value={result.deltas.expected_loss} fmt={money} />,
    },
  ];

  const maxRate = Math.max(...result.calibration.map((b) => b.actual_default_rate ?? 0), 0.01);

  return (
    <div className="mt-3 rounded-sm border border-border">
      <div className="border-b border-border bg-surface-2 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-ink-muted">
        Back-test — {result.book.size.toLocaleString()} historic loans · base default rate {pct(result.book.base_default_rate)}
      </div>

      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-border font-mono text-[10px] uppercase tracking-wide text-ink-muted">
            <th className="px-2.5 py-1.5 text-left">Metric</th>
            <th className="px-2.5 py-1.5 text-right">v{result.active_version}</th>
            <th className="px-2.5 py-1.5 text-right">v{result.draft_version}</th>
            <th className="px-2.5 py-1.5 text-right">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-border">
              <td className="px-2.5 py-1.5 text-ink-muted">{row.label}</td>
              <td className="px-2.5 py-1.5 text-right font-mono tabular-nums">{row.active}</td>
              <td className="px-2.5 py-1.5 text-right font-mono tabular-nums">{row.draft}</td>
              <td className="px-2.5 py-1.5 text-right font-mono tabular-nums">{row.delta}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="px-2.5 py-2">
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-ink-muted">
          Calibration — predicted score vs actual default rate
        </p>
        <div className="flex flex-col gap-1">
          {result.calibration.map((b) => (
            <div key={b.score_range} className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-right font-mono text-[11px] text-ink-muted">{b.score_range}</span>
              <div className="h-2 flex-1 rounded-full bg-surface-2">
                <div
                  className="h-2 rounded-full bg-accent"
                  style={{ width: `${Math.round(((b.actual_default_rate ?? 0) / maxRate) * 100)}%` }}
                />
              </div>
              <span className="w-20 shrink-0 text-right font-mono text-[11px] tabular-nums">
                {pct(b.actual_default_rate)} <span className="text-ink-muted">(n={b.count})</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="border-t border-border px-2.5 py-1.5 text-[10.5px] leading-snug text-ink-muted">{result.book.caveat}</p>
    </div>
  );
}
