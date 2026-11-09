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
  /** Absent on runs saved before samples existed. */
  sample?: boolean;
  /** The run whose decisions were marked again, with no model calls. */
  rescored_from?: string;
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

export interface RankedPlaybook {
  doc: string;
  section: string | null;
  score: number;
}

export interface RetrievedUnit {
  doc: string;
  kind: string;
  section: string | null;
  score: number;
}

export interface RetrievalTicket {
  id: string;
  title: string;
  family: string;
  expected: string | null;
  top: string | null;
  score: number | null;
  hit: boolean;
  false_match: boolean;
  rank: number | null;
  right_score: number | null;
  best_wrong_score: number | null;
  ranked: RankedPlaybook[];
  also: RetrievedUnit[];
}

export interface ScoredSet extends RetrievalRun {
  tickets: RetrievalTicket[];
}

export type Measure =
  "hit_rate" | "mean_reciprocal_rank" | "recall" | "false_match_rate";

export interface PathResult {
  run: string;
  n: number;
  path_accuracy: number;
  path_margin: number;
  cost_per_ticket_chf: number;
}

export interface RetrievalView {
  sets: { dev: ScoredSet | null; unseen_dev: ScoredSet | null };
  history: Pick<
    RetrievalRun,
    "id" | "date" | "set" | "kb_version" | "summary"
  >[];
  questions: Record<Measure, string>;
  floors: Partial<Record<Measure, number>>;
  rule: {
    sure: number;
    threshold: number;
    margin: number;
    support: number;
    top_k: number;
  };
  embedding_model: string;
  kb_version: string;
  decision: {
    with_search: PathResult | null;
    without_search: PathResult | null;
  };
}

export interface SearchResult {
  ranked: RankedPlaybook[];
  why: "sure" | "clear" | null;
  given: (RetrievedUnit & { highlights: { text: string; score: number }[] })[];
}

export interface Evaluations {
  runs: Evaluation[];
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

export type QueueState = "queued" | "working" | "review" | "closed" | "failed";

export type Verdict = "approved" | "corrected" | "rejected";

export interface QueueDecision {
  path: Path;
  cause: string;
  reasoning: string;
  tool: string | null;
  tool_input: Record<string, string> | null;
  queue: string | null;
  priority: string | null;
  summary: string | null;
  retrieved: { doc: string; section: string | null; score: number }[];
}

export interface QueueReview {
  verdict: Verdict;
  seconds: number;
  queue: string | null;
  note: string;
  outcome: { detail: string; ticket_number?: string; queue?: string };
  at: string;
}

export interface QueueTicket {
  id: string;
  batch: string;
  title: string;
  description: string;
  priority: string;
  sla_plan: string;
  submitted_at: string;
  applications: string[];
  requester: {
    id: string;
    name: string;
    department: string | null;
    office: string | null;
    device: string | null;
  };
  state: QueueState;
  decision: QueueDecision | null;
  agent_seconds: number | null;
  cost_chf: number | null;
  trace_id: string | null;
  trace_url: string | null;
  review: QueueReview | null;
  error: string | null;
}

export interface QueueValue {
  model_cost_chf: number;
  agent_seconds: number | null;
  reviewed: number;
  approved: number;
  review_seconds: number | null;
  minutes_saved: number;
  net_chf: number;
  minutes_by_hand: number;
  chf_per_hour: number;
}

export interface QueueView {
  tickets: QueueTicket[];
  counts: Record<QueueState, number>;
  at_desk: number;
  batch_size: number;
  queues: string[];
  value: QueueValue;
}

export interface ReviewBody {
  verdict: Verdict;
  seconds: number;
  queue?: string;
  note?: string;
}

export interface TraceStep {
  name: string;
  type: string;
  start_ms: number;
  duration_ms: number;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
}

export interface Trace {
  status: "off" | "pending" | "ready";
  url: string | null;
  steps: TraceStep[];
}

/** The four paths a decision can take. "NO_TOOLS" is a comparison only. */
export type RoutePath = Exclude<Path, "NO_TOOLS">;

export interface StationInfo {
  name: string;
  does: string;
  cannot: string;
  code: string;
  gate: boolean;
}

export interface Line {
  path: RoutePath;
  label: string;
  means: string;
  stations: string[];
  otherwise: string[];
  otherwise_when: string;
}

export interface Example {
  id: string;
  title: string;
  family: string;
  cause: string;
  retrieved: string[];
  tool: string | null;
  queue: string | null;
}

export interface ToolInfo {
  name: string;
  does: string;
  tier: "routine" | "sensitive";
  owner: string | null;
  escalation: boolean;
}

export interface Overview {
  goal: {
    sentence: string;
    worth_it: string;
    minutes_by_hand: number;
    review_minutes: number;
    chf_per_hour: number;
    break_even: number;
  };
  result: {
    run: string;
    date: string;
    n: number;
    path_accuracy: number;
    path_margin: number;
    cost_per_ticket_chf: number;
    time_per_ticket_sec: number;
    classifier_path_accuracy: number;
  } | null;
  trunk: string[];
  lines: Line[];
  stations: Record<string, StationInfo>;
  examples: Partial<Record<RoutePath, Example>>;
  model: {
    name: string;
    input_usd_per_million: number | null;
    output_usd_per_million: number | null;
    calls_per_ticket: number;
    how: string;
    why: string;
  };
  tools: ToolInfo[];
  tiers: Record<string, string>;
  queues: string[];
  services: {
    name: string;
    holds: string;
    truth: boolean;
    connected: boolean;
  }[];
  limits: string[];
  versions: Record<string, string>;
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
  overview: () => request<Overview>("/api/overview"),
  retrieval: () => request<RetrievalView>("/api/retrieval"),
  search: (text: string) =>
    post<SearchResult>("/api/retrieval/search", { text }),
  queue: () => request<QueueView>("/api/queue"),
  loadBatch: () => post<QueueView>("/api/queue/load", {}),
  review: (id: string, body: ReviewBody) =>
    post<QueueTicket>(`/api/queue/tickets/${id}/review`, body),
  trace: (id: string) => request<Trace>(`/api/queue/tickets/${id}/trace`),
};
