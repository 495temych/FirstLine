export type Path =
  "SELF_SERVE" | "AUTO_FIX" | "ESCALATE" | "OUT_OF_SCOPE" | "NO_TOOLS";

export interface Highlight {
  text: string;
  score: number;
}

export interface Unit {
  doc: string;
  section: string | null;
  text: string;
  score: number;
  highlights: Highlight[];
}

export interface DraftTicket {
  source: "escalate" | "self_serve" | "decline";
  queue: string;
  priority: string;
  summary: string;
  declined_tool?: string;
  reason?: string;
  diagnostic_summary?: string;
}

export type Pending =
  | { kind: "confirm_fix"; tool_name: string; tool_input: object }
  | { kind: "confirm_ticket"; ticket: DraftTicket }
  | { kind: "self_serve" };

export type Gate = Pending["kind"];

export interface ToolResult {
  detail: string;
  timestamp: string;
  ticket_number?: string;
  queue?: string;
}

export interface Run {
  id: string;
  query: string;
  use_retrieval: boolean;
  retrieved: Unit[];
  path: Path;
  reasoning: string;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  human_decision: { fix?: boolean; ticket?: boolean; resolved?: boolean };
  ticket_draft: DraftTicket | null;
  tool_result: ToolResult | null;
  pending: Pending | null;
}

export interface Decisions {
  n: number;
  path_accuracy: number;
  path_margin: number;
  action_accuracy: number;
  action_margin: number;
  team_accuracy: number | null;
  team_margin: number | null;
  mistake_cost_chf: number;
  kappa: number | null;
}

export interface Summary extends Decisions {
  cause_accuracy: number | null;
  retrieval_accuracy: number;
  automation_rate: number;
  cost_per_ticket_usd: number | null;
  cost_per_ticket_chf: number | null;
  time_per_ticket_sec: number;
}

export interface PathMeasures {
  precision: number | null;
  recall: number | null;
  n: number;
}

export interface ScoredTicket {
  id: string;
  text: string;
  difficulty: string;
  expected_paths: string[];
  expected_tools: string[];
  expected_queues: string[];
  path: string;
  tool: string | null;
  queue: string | null;
  action_correct: boolean;
  mistake_cost_chf: number;
  error: string | null;
}

export interface Evaluation {
  id: string;
  date: string;
  set: string;
  tiny: boolean;
  model: string;
  version: string;
  kb_version: string;
  summary: Summary;
  yardsticks: { most_common: Decisions; classifier: Decisions };
  confusion: Record<string, Record<string, number>>;
  per_path: Record<string, PathMeasures>;
  by_difficulty: Record<string, Summary>;
  by_family: Record<string, Summary>;
  tickets: ScoredTicket[];
}

export interface RetrievalSummary {
  n: number;
  covered: number;
  uncovered: number;
  hit_rate: number | null;
  mean_reciprocal_rank?: number | null;
  recall?: number | null;
  false_match_rate: number | null;
}

export interface RetrievalFamily extends RetrievalSummary {
  name: string;
  doc: string | null;
}

export interface RetrievalRun {
  id: string;
  date: string;
  set: string;
  kb_version: string;
  threshold: number;
  top_k: number;
  summary: RetrievalSummary;
  by_family: Record<string, RetrievalFamily>;
}

export interface Evaluations {
  runs: Evaluation[];
  retrieval: RetrievalRun[];
  costs: { security: number; wrong: number; minor: number };
}

export interface Answer {
  paths: string[];
  tools: string[];
  queues: string[];
  units: string[];
  difficulty: string;
  note: string;
  family: string;
  cause: string | null;
  checks: string[];
  root_cause?: string;
}

export interface Requester {
  id: string;
  name: string;
  department: string;
  floor: number;
  lockouts_24h: number;
  device: {
    id: string;
    model: string;
    image: string;
    age_years: number;
    battery_health: number;
  };
  groups: string[];
  recent_tickets: string[];
}

export interface LabelledTicket {
  id: string;
  text: string;
  answer: Answer;
  requester: Requester;
  latest: ScoredTicket | null;
}

export interface Stats {
  n: number;
  paths: string[];
  counts: Record<string, number>;
  pct: Record<string, number>;
  automation_rate: number | null;
  avg_response_time_sec: Record<string, number | null>;
  low_sample: boolean;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (response.ok) return (await response.json()) as T;
  const failure = (await response.json().catch(() => ({}))) as {
    detail?: unknown;
  };
  throw new Error(
    typeof failure.detail === "string"
      ? failure.detail
      : `The server answered ${response.status.toString()}. Check that the backend is running.`,
  );
}

function post<T>(url: string, body: object): Promise<T> {
  return request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  health: () => request<{ api_key: boolean }>("/api/health"),
  startTriage: (text: string, useRetrieval: boolean) =>
    post<Run>("/api/triage", { text, use_retrieval: useRetrieval }),
  readRun: (id: string) => request<Run>(`/api/runs/${id}`),
  answerGate: (id: string, gate: Gate, approved: boolean) =>
    post<Run>(`/api/runs/${id}/answer`, { gate, approved }),
  evaluations: () => request<Evaluations>("/api/evaluations"),
  tickets: () => request<LabelledTicket[]>("/api/tickets"),
  stats: () => request<Stats>("/api/stats"),
};
