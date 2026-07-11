import type { AgentMessage } from "../types";

const AGENT_LABEL: Record<string, string> = {
  eligibility: "Eligibility",
  affordability: "Affordability",
  risk: "Risk",
  orchestrator: "Orchestrator",
};

const AGENT_COLOR: Record<string, string> = {
  eligibility: "text-ink-muted",
  affordability: "text-accent",
  risk: "text-refer",
  orchestrator: "text-ink",
};

const TYPE_LABEL: Record<string, string> = {
  assessment: "assessment",
  flag_concern: "flag concern",
  request_review: "request review",
  provide_context: "reassessed",
  escalate: "escalate",
};

export function AgentConversation({ messages }: { messages: AgentMessage[] }) {
  if (messages.length === 0) {
    return <p className="text-sm text-ink-muted">Agent conversation will appear here once reasoning starts.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {messages.map((m, i) => (
        <div key={i} className="rounded-sm border border-border bg-surface px-3 py-2">
          <div className="flex items-center gap-1.5 font-mono text-[11px]">
            <span className={`font-semibold ${AGENT_COLOR[m.from_agent] ?? "text-ink"}`}>{AGENT_LABEL[m.from_agent] ?? m.from_agent}</span>
            {m.to_agent && (
              <>
                <span className="text-ink-muted">&rarr;</span>
                <span className={AGENT_COLOR[m.to_agent] ?? "text-ink"}>{AGENT_LABEL[m.to_agent] ?? m.to_agent}</span>
              </>
            )}
            <span
              className={`ml-1 rounded-sm px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
                m.message_type === "flag_concern" || m.message_type === "escalate" ? "bg-refer-soft text-refer" : "bg-surface-2 text-ink-muted"
              }`}
            >
              {TYPE_LABEL[m.message_type] ?? m.message_type}
            </span>
          </div>
          <p className="mt-1 text-[13px] leading-snug">{m.content}</p>
        </div>
      ))}
    </div>
  );
}
