import { expect, it } from "vitest";
import type { Run } from "./api";
import { answers, checklist, spent } from "./steps";
import { baseRun } from "./test-data";

const running = (next: string[], more: Partial<Run> = {}): Run => ({
  ...baseRun,
  path: "",
  status: "running",
  pending: null,
  steps: [],
  retrieved: [],
  next,
  ...more,
});

const labels = (run: Run) => checklist(run).map((i) => `${i.state} ${i.label}`);

it("starts with the search running and the rest still to come", () => {
  expect(labels(running(["retrieve"]))).toEqual([
    "running Search the knowledge base",
    "pending Decide",
    "pending Apply the rules",
  ]);
});

it("shows each lookup as it lands while the model chooses the next", () => {
  const run = running(["investigate"], {
    retrieved: baseRun.retrieved,
    steps: baseRun.steps.slice(0, 1),
  });
  expect(labels(run)).toEqual([
    "done Search the knowledge base",
    "done Look up the requester",
    "running Choose the next step",
    "pending Decide",
    "pending Apply the rules",
  ]);
  expect(checklist(run)[0]?.result).toBe("Found vpn.");
});

it("names each lookup in plain words, and marks a refused one", () => {
  const [step] = baseRun.steps;
  const calls = [
    { ...step, id: "a", tool: "search_kb", input: { query: "vpn drops" } },
    { ...step, id: "b", tool: "find_similar_incidents", input: { query: "q" } },
    {
      ...step,
      id: "c",
      tool: "run_check",
      input: { step: "vpn-client-check" },
    },
    { ...step, id: "d", tool: "unlock_ad_account", ok: false },
  ];
  const items = checklist({ ...baseRun, steps: calls });
  expect(items.slice(1, 5).map((i) => `${i.state} ${i.label}`)).toEqual([
    "done Search again for “vpn drops”",
    "done Find similar past tickets",
    "done Run the check vpn-client-check",
    "failed Call unlock_ad_account",
  ]);
});

it("runs the rules after the decision, and shows a rule that changed it", () => {
  const deciding = running(["enforce"], { path: "AUTO_FIX" });
  expect(labels(deciding).slice(-2)).toEqual([
    "done Decide",
    "running Apply the rules",
  ]);
  const changed: Run = {
    ...baseRun,
    rule: {
      rule: "SEC-04",
      reason: "2 lockouts in 24 hours.",
      code: "sec04 in agent/rules.py",
      proposed: {
        path: "AUTO_FIX",
        tool_name: "unlock_ad_account",
        tool_input: {},
      },
    },
    path: "ESCALATE",
  };
  const items = checklist(changed);
  expect(items.at(-2)?.result).toBe("Auto-fix: unlock_ad_account");
  expect(items.at(-1)).toMatchObject({
    state: "rule",
    label: "Apply the rules: SEC-04 changed it",
    result: "2 lockouts in 24 hours.",
  });
  expect(checklist(baseRun).at(-1)?.result).toBe(
    "No rule changed the decision.",
  );
});

it("says when the loop stopped at its limit", () => {
  const run: Run = {
    ...baseRun,
    path: "ESCALATE",
    stopped: "lookups",
    tool_input: { queue: "DESK-SUPPORT" },
  };
  expect(checklist(run).at(-2)).toMatchObject({
    label: "Stop at the limit",
    state: "failed",
    result: "Stopped before deciding, so it goes to DESK-SUPPORT.",
  });
});

it("shows a failure, a run without the knowledge base and one call", () => {
  const failed = running(["investigate"], { status: "failed", error: "Boom" });
  expect(checklist(failed).at(-1)).toMatchObject({
    state: "failed",
    result: "Boom",
  });
  const off: Run = {
    ...baseRun,
    use_retrieval: false,
    path: "NO_TOOLS",
    steps: [],
  };
  expect(labels(off)).toEqual([
    "done Search the knowledge base",
    "done Answer without tools",
  ]);
  const oneCall = running(["triage"], { design: "one call" });
  expect(labels(oneCall).slice(1)).toEqual([
    "running Decide",
    "pending Apply the rules",
  ]);
  const escalation: Run = {
    ...baseRun,
    path: "ESCALATE",
    tool_input: { queue: "SEC-INCIDENT" },
  };
  expect(checklist(escalation).at(-2)?.result).toBe("Escalate: SEC-INCIDENT");
  expect(checklist(running(["at_limit"])).at(-1)?.state).toBe("running");
  expect(checklist(running(["confirm_fix"])).at(-1)?.state).toBe("pending");
});

it("lists the answers given at the gates, in order", () => {
  const run: Run = {
    ...baseRun,
    human_decision: { fix: false, ticket: true },
  };
  expect(answers(run).map((a) => a.text)).toEqual([
    "Decline fix",
    "Create ticket",
  ]);
  expect(
    answers({ ...baseRun, human_decision: { resolved: false, ticket: false } }),
  ).toEqual([
    { gate: "self_serve", text: "It didn't, escalate to a technician" },
    { gate: "confirm_ticket", text: "Don't create ticket" },
  ]);
  expect(
    answers({ ...baseRun, human_decision: { fix: true, resolved: true } }).map(
      (a) => a.text,
    ),
  ).toEqual(["Run fix", "This resolved it"]);
});

it("gives a step's time, and its cost when it has one", () => {
  const [step] = baseRun.steps;
  expect(spent(step)).toBe("1.1 s, CHF 0.0009");
  expect(spent({ ...step, cost_chf: 0 })).toBe("1.1 s");
});
