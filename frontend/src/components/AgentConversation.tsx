import type { AgentMessage, AgentThinking } from "../types";

const AGENT_LABEL: Record<string, string> = {
  eligibility: "Eligibility",
  affordability: "Affordability",
  risk: "Risk",
  orchestrator: "Orchestrator",
  explanation: "Explanation",
};

/** Text color, avatar background, and card accent border per agent. */
const AGENT_STYLE: Record<string, { text: string; avatar: string; border: string }> = {
  eligibility: { text: "text-approve", avatar: "bg-approve", border: "border-l-approve" },
  affordability: { text: "text-accent", avatar: "bg-accent", border: "border-l-accent" },
  risk: { text: "text-refer", avatar: "bg-refer", border: "border-l-refer" },
  orchestrator: { text: "text-ink", avatar: "bg-ink-muted", border: "border-l-border" },
  explanation: { text: "text-ink-muted", avatar: "bg-ink-muted", border: "border-l-border" },
};

const FALLBACK_STYLE = { text: "text-ink", avatar: "bg-ink-muted", border: "border-l-border" };

const TYPE_BADGE: Record<string, { label: string; cls: string }> = {
  assessment: { label: "assessment", cls: "bg-surface-2 text-ink-muted" },
  flag_concern: { label: "challenge", cls: "bg-refer-soft text-refer" },
  request_review: { label: "request review", cls: "bg-surface-2 text-ink-muted" },
  provide_context: { label: "reassessed", cls: "bg-accent-soft text-accent" },
  escalate: { label: "escalate", cls: "bg-refer-soft text-refer" },
};

function Avatar({ agent }: { agent: string }) {
  const style = AGENT_STYLE[agent] ?? FALLBACK_STYLE;
  return (
    <span
      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-bold text-white ${style.avatar}`}
    >
      {(AGENT_LABEL[agent] ?? agent).charAt(0)}
    </span>
  );
}

/** "adequate (score 0.85, confidence 0.90): long reasoning…" -> bold headline + body. */
function splitContent(content: string): { headline: string | null; body: string } {
  const idx = content.indexOf(": ");
  if (idx > 0 && idx <= 90) {
    return { headline: content.slice(0, idx), body: content.slice(idx + 2) };
  }
  return { headline: null, body: content };
}

function MessageCard({ m }: { m: AgentMessage }) {
  const style = AGENT_STYLE[m.from_agent] ?? FALLBACK_STYLE;
  const badge = TYPE_BADGE[m.message_type] ?? { label: m.message_type, cls: "bg-surface-2 text-ink-muted" };
  const { headline, body } = splitContent(m.content);
  const refs = [...new Set(m.evidence_refs)].filter(Boolean);

  return (
    <div className={`rounded-sm border border-border border-l-2 bg-surface px-3.5 py-2.5 ${style.border}`}>
      <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
        <Avatar agent={m.from_agent} />
        <span className={`font-semibold ${style.text}`}>{AGENT_LABEL[m.from_agent] ?? m.from_agent}</span>
        {m.to_agent && (
          <>
            <span className="text-ink-muted">&rarr;</span>
            <Avatar agent={m.to_agent} />
            <span className={`font-semibold ${(AGENT_STYLE[m.to_agent] ?? FALLBACK_STYLE).text}`}>
              {AGENT_LABEL[m.to_agent] ?? m.to_agent}
            </span>
          </>
        )}
        <span className={`rounded-sm px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${badge.cls}`}>{badge.label}</span>
      </div>
      {headline && <p className="mt-2 text-[13px] font-semibold leading-snug">{headline}</p>}
      <p className={`${headline ? "mt-1" : "mt-2"} max-w-[72ch] text-[13px] leading-relaxed text-ink`}>{body}</p>
      {refs.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10px] uppercase tracking-wide text-ink-muted">cites</span>
          {refs.map((r) => (
            <span key={r} className="rounded-sm bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ThinkingCard({ t }: { t: AgentThinking }) {
  const style = AGENT_STYLE[t.agent] ?? FALLBACK_STYLE;
  return (
    <div className={`rounded-sm border border-dashed border-border border-l-2 bg-surface px-3.5 py-2.5 ${style.border}`}>
      <div className="flex items-center gap-2 font-mono text-[11px]">
        <Avatar agent={t.agent} />
        <span className={`font-semibold ${style.text}`}>{AGENT_LABEL[t.agent] ?? t.agent}</span>
        <span className="rounded-sm bg-surface-2 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink-muted">thinking</span>
        <span className="flex gap-0.5" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className={`h-1 w-1 animate-bounce rounded-full ${style.avatar}`}
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </span>
      </div>
      <p className="mt-2 text-[13px] italic leading-relaxed text-ink-muted">{t.note}</p>
    </div>
  );
}

export function AgentConversation({ messages, thinking = [] }: { messages: AgentMessage[]; thinking?: AgentThinking[] }) {
  if (messages.length === 0 && thinking.length === 0) {
    return <p className="text-sm text-ink-muted">Agent conversation will appear here once reasoning starts.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {messages.map((m, i) => (
        <MessageCard key={i} m={m} />
      ))}
      {thinking.map((t) => (
        <ThinkingCard key={t.agent} t={t} />
      ))}
    </div>
  );
}
