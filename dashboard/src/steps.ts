import type { Gate, Run, Step } from "./run";
import { pathLabels } from "./format";

export type ItemState = "done" | "failed" | "running" | "pending" | "rule";

/** One line of the checklist under the agent's reply. */
export interface Item {
  key: string;
  label: string;
  state: ItemState;
  result?: string;
  step?: Step;
}

const DECIDE = "record_decision";

/** What each lookup does, in a technician's words. */
function lookupLabel(step: Step): string {
  const input = step.input;
  const text = (key: string) =>
    typeof input[key] === "string" ? input[key] : "";
  switch (step.tool) {
    case "search_kb":
      return `Search again for “${text("query")}”`;
    case "lookup_requester":
      return "Look up the requester";
    case "find_similar_incidents":
      return "Find similar past tickets";
    case "run_check":
      return `Run the check ${text("step")}`;
    default:
      return `Call ${step.tool}`;
  }
}

function search(run: Run): Item {
  if (!run.use_retrieval) {
    return {
      key: "search",
      label: "Search the knowledge base",
      state: "done",
      result: "Switched off for this ticket.",
    };
  }
  if (run.next.includes("retrieve")) {
    return {
      key: "search",
      label: "Search the knowledge base",
      state: "running",
    };
  }
  const docs = [...new Set(run.retrieved.map((unit) => unit.doc))];
  return {
    key: "search",
    label: "Search the knowledge base",
    state: "done",
    result: docs.length
      ? `Found ${docs.join(", ")}.`
      : "Nothing matched closely enough.",
  };
}

/** The decision the model made, before any rule changed it. */
function proposal(run: Run): string {
  const made = run.rule?.proposed ?? {
    path: run.path,
    tool_name: run.tool_name,
    tool_input: run.tool_input,
  };
  const queue = made.tool_input?.queue;
  const team = typeof queue === "string" ? queue : null;
  const detail = made.path === "ESCALATE" ? team : made.tool_name;
  const label = pathLabels[made.path] ?? made.path;
  return detail ? `${label}: ${detail}` : label;
}

function decision(run: Run): Item {
  const step = run.steps.find((s) => s.tool === DECIDE);
  if (run.stopped) {
    return {
      key: "decide",
      label: "Stop at the limit",
      state: "failed",
      result: `Stopped before deciding, so it goes to ${String(run.tool_input?.queue)}.`,
    };
  }
  return {
    key: "decide",
    label: "Decide",
    state: step && !step.ok ? "failed" : "done",
    result: proposal(run),
    step,
  };
}

function rules(run: Run): Item {
  if (run.rule) {
    return {
      key: "rules",
      label: `Apply the rules: ${run.rule.rule} changed it`,
      state: "rule",
      result: run.rule.reason,
    };
  }
  return {
    key: "rules",
    label: "Apply the rules",
    state: "done",
    result: "No rule changed the decision.",
  };
}

/** The step the agent is on while the run works, from the graph's next node. */
function working(run: Run): Item[] {
  if (run.next.includes("investigate")) {
    return [
      { key: "think", label: "Choose the next step", state: "running" },
      { key: "decide", label: "Decide", state: "pending" },
      { key: "rules", label: "Apply the rules", state: "pending" },
    ];
  }
  if (run.next.includes("triage") || run.next.includes("no_tools")) {
    return [
      { key: "decide", label: "Decide", state: "running" },
      { key: "rules", label: "Apply the rules", state: "pending" },
    ];
  }
  if (run.next.includes("enforce") || run.next.includes("at_limit")) {
    return [{ key: "rules", label: "Apply the rules", state: "running" }];
  }
  return [
    { key: "decide", label: "Decide", state: "pending" },
    { key: "rules", label: "Apply the rules", state: "pending" },
  ];
}

/** The agent's steps so far, in order, with the ones still to come. */
export function checklist(run: Run): Item[] {
  const items = [search(run)];
  const lookups = run.steps.filter((s) => s.tool !== DECIDE);
  items.push(
    ...lookups.map((step) => ({
      key: step.id,
      label: lookupLabel(step),
      state: step.ok ? ("done" as const) : ("failed" as const),
      result: step.result,
      step,
    })),
  );
  if (run.status === "failed") {
    items.push({
      key: "failed",
      label: "Stopped by an error",
      state: "failed",
      result: run.error ?? "The run failed.",
    });
    return items;
  }
  if (run.status === "running" && !run.path) {
    return [...items, ...working(run)];
  }
  if (run.path === "NO_TOOLS") {
    items.push({
      key: "decide",
      label: "Answer without tools",
      state: "done",
      result: "With the knowledge base off, there's no path to choose.",
    });
    return items;
  }
  items.push(decision(run));
  items.push(
    run.next.includes("enforce")
      ? { key: "rules", label: "Apply the rules", state: "running" }
      : rules(run),
  );
  return items;
}

/** What a person answered at each gate, in the order they answered. */
export function answers(run: Run): { gate: Gate; text: string }[] {
  const said = run.human_decision;
  const out: { gate: Gate; text: string }[] = [];
  if (said.fix !== undefined) {
    out.push({
      gate: "confirm_fix",
      text: said.fix ? "Run fix" : "Decline fix",
    });
  }
  if (said.resolved !== undefined) {
    out.push({
      gate: "self_serve",
      text: said.resolved
        ? "This resolved it"
        : "It didn't, escalate to a technician",
    });
  }
  if (said.ticket !== undefined) {
    out.push({
      gate: "confirm_ticket",
      text: said.ticket ? "Create ticket" : "Don't create ticket",
    });
  }
  return out;
}

/** Time and cost of a step, as "1.1 s, CHF 0.0009". */
export function spent(step: Step): string {
  const time = `${step.time_sec.toFixed(1)} s`;
  return step.cost_chf ? `${time}, CHF ${step.cost_chf.toFixed(4)}` : time;
}
