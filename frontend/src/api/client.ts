import type { Applicant, DecisionRecord, Policy, PolicyDraft, SimulateResult } from "../types";

export async function fetchApplicants(): Promise<Applicant[]> {
  const res = await fetch("/api/applicants");
  return res.json();
}

export async function fetchDecisions(applicantId?: string): Promise<DecisionRecord[]> {
  const url = applicantId ? `/api/decisions?applicant_id=${encodeURIComponent(applicantId)}` : "/api/decisions";
  const res = await fetch(url);
  return res.json();
}

export async function decideBnpl(applicantId: string): Promise<DecisionRecord> {
  const res = await fetch("/api/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ applicant_id: applicantId, product: "bnpl" }),
  });
  if (!res.ok) throw new Error(`Decision request failed: ${res.status}`);
  return res.json();
}

export interface SsePipelineEvent {
  event: string;
  data: Record<string, unknown>;
}

/** Streams the personal_loan SSE pipeline, invoking onEvent for each event until 'done'. */
export async function decidePersonalLoan(applicantId: string, onEvent: (evt: SsePipelineEvent) => void): Promise<void> {
  const res = await fetch("/api/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ applicant_id: applicantId, product: "personal_loan" }),
  });
  if (!res.ok || !res.body) throw new Error(`Decision request failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // sse_starlette emits CRLF line endings; normalize before splitting on blank lines.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) {
        onEvent({ event, data: JSON.parse(data) });
      }
      if (event === "done") return;
    }
  }
}

export async function fetchActivePolicy(): Promise<Policy> {
  const res = await fetch("/api/policy/active");
  return res.json();
}

export async function fetchDrafts(): Promise<PolicyDraft[]> {
  const res = await fetch("/api/policy/drafts");
  return res.json();
}

export async function simulatePolicy(filename: string, product: string): Promise<SimulateResult> {
  const res = await fetch("/api/policy/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, product }),
  });
  if (!res.ok) throw new Error(`Simulate failed: ${res.status}`);
  return res.json();
}

export async function activatePolicy(filename: string, approvedBy: string): Promise<Policy> {
  const res = await fetch("/api/policy/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, approved_by: approvedBy }),
  });
  if (!res.ok) throw new Error(`Activate failed: ${res.status}`);
  return res.json();
}

export async function rollbackPolicy(): Promise<Policy> {
  const res = await fetch("/api/policy/rollback", { method: "POST" });
  if (!res.ok) throw new Error(`Rollback failed: ${res.status}`);
  return res.json();
}
