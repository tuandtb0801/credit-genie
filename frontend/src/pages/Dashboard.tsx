import { useEffect, useState } from "react";
import { decideBnpl, decidePersonalLoan, fetchApplicants } from "../api/client";
import { AgentConversation } from "../components/AgentConversation";
import { ApplicantPicker } from "../components/ApplicantPicker";
import { DecisionCard } from "../components/DecisionCard";
import { PipelineViz } from "../components/PipelineViz";
import type { Applicant, AgentMessage, DecisionRecord, PipelineStage, Product, StageName } from "../types";

const STAGE_ORDER: StageName[] = ["ingest", "reason", "score", "explain"];

function initialStages(): PipelineStage[] {
  return STAGE_ORDER.map((stage) => ({ stage, status: "pending" }));
}

export function Dashboard() {
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [product, setProduct] = useState<Product>("personal_loan");
  const [stages, setStages] = useState<PipelineStage[]>(initialStages());
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [record, setRecord] = useState<DecisionRecord | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApplicants().then((list) => {
      setApplicants(list);
      if (list.length > 0) {
        setSelectedId(list[0].applicant_id);
        setProduct(list[0].products[0]);
      }
    });
  }, []);

  function selectApplicant(id: string) {
    setSelectedId(id);
    const applicant = applicants.find((a) => a.applicant_id === id);
    if (applicant) setProduct(applicant.products[0]);
    setRecord(null);
    setMessages([]);
    setStages(initialStages());
    setError(null);
  }

  async function runDecision() {
    if (!selectedId) return;
    setRunning(true);
    setError(null);
    setRecord(null);
    setMessages([]);
    setStages(initialStages());

    try {
      if (product === "bnpl") {
        const result = await decideBnpl(selectedId);
        setStages(STAGE_ORDER.map((stage) => ({ stage, status: "done" })));
        setRecord(result);
      } else {
        await decidePersonalLoan(selectedId, (evt) => {
          if (evt.event === "stage_start") {
            const stage = evt.data.stage as StageName;
            setStages((prev) => prev.map((s) => (s.stage === stage ? { ...s, status: "active" } : s)));
          } else if (evt.event === "stage_complete") {
            const stage = evt.data.stage as StageName;
            setStages((prev) => prev.map((s) => (s.stage === stage ? { ...s, status: "done", timing_ms: evt.data.timing_ms as number } : s)));
          } else if (evt.event === "agent_message") {
            setMessages((prev) => [...prev, evt.data as unknown as AgentMessage]);
          } else if (evt.event === "decision_made") {
            setRecord(evt.data as unknown as DecisionRecord);
          } else if (evt.event === "error") {
            setError((evt.data.message as string) ?? "Decision failed.");
          }
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="grid grid-cols-[280px_1fr] gap-6">
      <aside>
        <ApplicantPicker applicants={applicants} selectedId={selectedId} product={product} onSelect={selectApplicant} onProductChange={setProduct} />
        <button
          onClick={runDecision}
          disabled={!selectedId || running}
          className="mt-4 w-full rounded-sm bg-accent px-3 py-2 font-mono text-[12px] font-semibold uppercase tracking-wide text-white disabled:opacity-40"
        >
          {running ? "Deciding…" : "Decide"}
        </button>
        {error && <p className="mt-2 text-[12px] text-decline">{error}</p>}
      </aside>

      <main className="flex flex-col gap-5">
        {product === "personal_loan" && (
          <section>
            <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-muted">Pipeline</h2>
            <PipelineViz stages={stages} />
          </section>
        )}

        {product === "personal_loan" && (
          <section>
            <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-muted">Agent Conversation</h2>
            <AgentConversation messages={messages} />
          </section>
        )}

        {record && (
          <section>
            <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-ink-muted">Decision</h2>
            <DecisionCard record={record} />
          </section>
        )}
      </main>
    </div>
  );
}
