import type { Outcome } from "../types";

const STYLES: Record<Outcome, string> = {
  APPROVE: "bg-approve-soft text-approve",
  DECLINE: "bg-decline-soft text-decline",
  REFER: "bg-refer-soft text-refer",
};

export function OutcomeBadge({ outcome, size = "md" }: { outcome: Outcome; size?: "sm" | "md" }) {
  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-sm font-mono font-semibold tracking-wide ${padding} ${STYLES[outcome]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {outcome}
    </span>
  );
}
