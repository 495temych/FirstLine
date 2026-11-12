import type { Path, Unit } from "./api";
import type { RuleOverride } from "./people";

/** One call the agent made in the loop, as the API keeps it. */
export interface Step {
  id: string;
  turn: number;
  tool: string;
  input: Record<string, unknown>;
  result: string;
  ok: boolean;
  time_sec: number;
  cost_chf: number | null;
}

/** A development ticket the Assistant offers, with its recorded checks. */
export interface TriageExample {
  id: string;
  title: string;
  text: string;
  requester: string;
}

export type RunStatus = "running" | "waiting" | "done" | "failed";

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
  /** Empty until the model has decided. */
  path: Path | "";
  reasoning: string;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  human_decision: { fix?: boolean; ticket?: boolean; resolved?: boolean };
  ticket_draft: DraftTicket | null;
  tool_result: ToolResult | null;
  pending: Pending | null;
  rule: RuleOverride | null;
  /** "loop" when the agent looked things up before deciding. */
  design: "one call" | "loop";
  steps: Step[];
  /** Why the loop stopped before deciding, if it did. */
  stopped: "lookups" | "cost" | null;
  requester: { id: string; department: string; office: string };
  status: RunStatus;
  error: string | null;
  /** The graph's next node while the run works, such as "investigate". */
  next: string[];
  /** The cause the model named, empty until it decides. */
  cause: string;
  response_time_sec: number | null;
  /** What the run's model calls cost, in francs; null when the price is unknown. */
  cost_chf: number | null;
}
