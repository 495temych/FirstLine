import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import { baseRun, result } from "./test-data";
import { Thread } from "./Thread";

afterEach(cleanup);

function show(run: Run = baseRun) {
  const onAnswer = vi.fn();
  render(<Thread run={run} busy={false} onAnswer={onAnswer} />);
  return onAnswer;
}

it("shows the request as the requester's message", () => {
  show();
  expect(screen.getByText("s.keller, Finance, Zürich")).toBeDefined();
  expect(
    screen.getByText("My VPN fails", { selector: ".query" }),
  ).toBeDefined();
});

it("shows the agent's steps as a list, each opening to its tool", () => {
  show();
  const list = screen.getByRole("list", { name: "The agent's steps" });
  const items = within(list).getAllByRole("listitem");
  expect(
    items.map((item) => item.querySelector(".check-label")?.textContent),
  ).toEqual([
    "Search the knowledge base",
    "Look up the requester",
    "Decide",
    "Apply the rules",
  ]);
  expect(items[0]?.textContent).toMatch(/^Done: Search the knowledge base/);
  expect(within(list).getByText("1.1 s, CHF 0.0009")).toBeDefined();
  expect(within(list).getByText("lookup_requester")).toBeDefined();
  expect(list.className).toContain("path-AUTO_FIX");
});

it("keeps the line grey and the gate shut while the agent works", () => {
  show({ ...baseRun, status: "running", path: "", next: ["investigate"] });
  const list = screen.getByRole("list", { name: "The agent's steps" });
  expect(list.className).toContain("undecided");
  expect(screen.getByText("Working")).toBeDefined();
  expect(screen.queryByRole("region", { name: "Waiting for you" })).toBeNull();
  expect(screen.queryByText("Knowledge used")).toBeNull();
});

it("holds the gate in a card, and answers it from there", () => {
  const onAnswer = show();
  const gate = screen.getByRole("region", { name: "Waiting for you" });
  fireEvent.click(within(gate).getByRole("button", { name: "Run fix" }));
  expect(onAnswer).toHaveBeenCalledWith("confirm_fix", true);
});

it("shows each answer as the person's message, then what happened", () => {
  show({
    ...baseRun,
    pending: null,
    status: "done",
    human_decision: { fix: true },
    tool_result: result,
  });
  expect(screen.getByText("You")).toBeDefined();
  expect(screen.getByText("Run fix", { selector: "p" })).toBeDefined();
  const outcome = screen.getByRole("region", { name: "What happened" });
  expect(within(outcome).getByText("Fix ran (simulated)")).toBeDefined();
});

it("shows a failed run without a decision or a gate", () => {
  show({ ...baseRun, status: "failed", error: "The run failed: Boom" });
  expect(screen.getByText("The run failed: Boom")).toBeDefined();
  expect(screen.queryByRole("region", { name: "What happened" })).toBeNull();
});

it("says when the agent decided in one call", () => {
  show({ ...baseRun, design: "one call", steps: [] });
  expect(screen.getByText("Decides in one call")).toBeDefined();
});
