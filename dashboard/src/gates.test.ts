import { describe, expect, it } from "vitest";
import type { Run } from "./api";
import { actionState } from "./gates";
import { baseRun, declined, draft } from "./test-data";

const run = (changes: Partial<Run>): Run => ({ ...baseRun, ...changes });
const ticketGate = { kind: "confirm_ticket", ticket: draft } as const;

describe("actionState", () => {
  it.each<[string, Partial<Run>, string]>([
    ["out of scope", { path: "OUT_OF_SCOPE", pending: null }, "out_of_scope"],
    ["no tools", { path: "NO_TOOLS", pending: null }, "no_tools"],
    ["a fix gate", {}, "await_fix"],
    [
      "self-serve",
      { path: "SELF_SERVE", pending: { kind: "self_serve" } },
      "await_self_serve",
    ],
    [
      "an escalation",
      { path: "ESCALATE", pending: ticketGate },
      "await_ticket",
    ],
    [
      "failed self-serve",
      { path: "SELF_SERVE", pending: ticketGate },
      "await_ticket",
    ],
    [
      "a declined fix",
      {
        pending: { kind: "confirm_ticket", ticket: declined },
        human_decision: { fix: false },
      },
      "await_declined_ticket",
    ],
    [
      "a resolved ticket",
      {
        path: "SELF_SERVE",
        pending: null,
        human_decision: { resolved: true },
      },
      "resolved",
    ],
    [
      "a confirmed fix",
      { pending: null, human_decision: { fix: true } },
      "fix_done",
    ],
    [
      "a confirmed ticket",
      {
        path: "ESCALATE",
        pending: null,
        human_decision: { ticket: true },
      },
      "ticket_done",
    ],
    [
      "a ticket after a declined fix",
      { pending: null, human_decision: { fix: false, ticket: true } },
      "ticket_done",
    ],
    [
      "a declined ticket",
      { pending: null, human_decision: { fix: false, ticket: false } },
      "skipped",
    ],
  ])("handles %s", (_name, changes, expected) => {
    expect(actionState(run(changes))).toBe(expected);
  });

  it("never reports a fix as done while a gate is waiting", () => {
    const waiting = run({ human_decision: { fix: true } });
    expect(actionState(waiting)).toBe("await_fix");
  });
});
