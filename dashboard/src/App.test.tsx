import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import { App } from "./App";
import { presets } from "./presets";
import {
  baseRun,
  declined,
  draft,
  evaluations,
  result,
  stats,
  tickets,
} from "./test-data";

type Reply = object | Error | number;

let replies: Partial<Record<string, Reply>>;
const calls: { url: string; body: unknown }[] = [];

function reply(url: string, init?: RequestInit) {
  const body = init?.body ? (JSON.parse(init.body as string) as unknown) : null;
  calls.push({ url, body });
  const answer = replies[url];
  if (answer instanceof Error) return Promise.reject(answer);
  if (typeof answer === "number") {
    return Promise.resolve(new Response("{}", { status: answer }));
  }
  return Promise.resolve(new Response(JSON.stringify(answer ?? {})));
}

beforeEach(() => {
  calls.length = 0;
  replies = {
    "/api/health": { status: "ok", api_key: true },
    "/api/triage": baseRun,
    "/api/evaluations": evaluations,
    "/api/tickets": tickets,
    "/api/stats": stats,
  };
  window.history.replaceState(null, "", "/");
  vi.stubGlobal("fetch", vi.fn(reply));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const click = (name: string | RegExp) => {
  fireEvent.click(screen.getByRole("button", { name }));
};

async function triage(run: Partial<Run> = {}) {
  replies["/api/triage"] = { ...baseRun, ...run };
  render(<App />);
  await screen.findByRole("button", { name: "Assistant" });
  fireEvent.change(screen.getByLabelText("Describe the issue"), {
    target: { value: "My VPN fails" },
  });
  click("Triage this ticket");
  await screen.findByText("My VPN fails", { selector: ".query" });
}

it("shows the three tabs and the example tickets", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "FirstLine" })).toBeDefined();
  for (const tab of ["Assistant", "Scoreboard", "Tickets"]) {
    expect(screen.getByRole("button", { name: tab })).toBeDefined();
  }
  expect(screen.getAllByRole("listitem")).toHaveLength(presets.length);
});

it("fills the ticket from an example without running it", () => {
  render(<App />);
  click(presets[1] ?? "");
  const box: HTMLTextAreaElement = screen.getByLabelText("Describe the issue");
  expect(box.value).toBe(presets[1]);
  expect(calls.some((c) => c.url === "/api/triage")).toBe(false);
});

it("sends the retrieval switch with the ticket", async () => {
  render(<App />);
  await screen.findByRole("button", { name: "Assistant" });
  fireEvent.click(screen.getByRole("switch"));
  fireEvent.change(screen.getByLabelText("Describe the issue"), {
    target: { value: "Help" },
  });
  click("Triage this ticket");
  await waitFor(() => {
    expect(calls.find((c) => c.url === "/api/triage")?.body).toEqual({
      text: "Help",
      use_retrieval: false,
    });
  });
});

it("blocks triage and explains when the key is missing", async () => {
  replies["/api/health"] = { status: "ok", api_key: false };
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "ANTHROPIC_API_KEY",
  );
  const button: HTMLButtonElement = screen.getByRole("button", {
    name: "Triage this ticket",
  });
  expect(button.disabled).toBe(true);
});

it("shows what was retrieved and why it matched", async () => {
  await triage();
  expect(screen.getByText("vpn")).toBeDefined();
  expect(screen.getByText("0.81")).toBeDefined();
  expect(
    screen.getByText("Reset the profile", { selector: ".highlights li" }),
  ).toBeDefined();
  expect(screen.getByText("Auto-fix")).toBeDefined();
});

it("waits at the fix gate and then shows the result", async () => {
  await triage();
  expect(
    screen.getByText("This fix won't run until you confirm it."),
  ).toBeDefined();
  replies["/api/runs/run1/answer"] = {
    ...baseRun,
    pending: null,
    human_decision: { fix: true },
    tool_result: result,
  };
  click("Run fix");
  expect(await screen.findByText("Fix ran (simulated)")).toBeDefined();
  expect(calls.at(-1)?.body).toEqual({ gate: "confirm_fix", approved: true });
  expect(window.location.search).toBe("?run=run1");
});

it("offers a pre-filled ticket after a declined fix", async () => {
  await triage();
  replies["/api/runs/run1/answer"] = {
    ...baseRun,
    human_decision: { fix: false },
    pending: { kind: "confirm_ticket", ticket: declined },
  };
  click("Decline fix");
  expect(await screen.findByText(/no new model call/)).toBeDefined();
  expect(screen.getByText("Profile is stale")).toBeDefined();
  expect(calls.at(-1)?.body).toEqual({ gate: "confirm_fix", approved: false });
  replies["/api/runs/run1/answer"] = {
    ...baseRun,
    pending: null,
    human_decision: { fix: false, ticket: true },
    tool_result: { ...result, ticket_number: "INC1234567" },
  };
  click("Create ticket");
  expect(await screen.findByText(/Ticket INC1234567 created/)).toBeDefined();
});

it("creates no ticket when an escalation is declined", async () => {
  await triage({
    path: "ESCALATE",
    pending: { kind: "confirm_ticket", ticket: draft },
  });
  expect(screen.getByText("SEC-INCIDENT")).toBeDefined();
  replies["/api/runs/run1/answer"] = {
    ...baseRun,
    path: "ESCALATE",
    pending: null,
    human_decision: { ticket: false },
  };
  click("Don't create ticket");
  expect(await screen.findByText("No ticket created.")).toBeDefined();
});

it("lets a self-serve answer be marked as resolved", async () => {
  await triage({ path: "SELF_SERVE", pending: { kind: "self_serve" } });
  replies["/api/runs/run1/answer"] = {
    ...baseRun,
    path: "SELF_SERVE",
    pending: null,
    human_decision: { resolved: true },
  };
  click("This resolved it");
  expect(await screen.findByText("Marked as resolved.")).toBeDefined();
});

it("takes no action out of scope", async () => {
  await triage({ path: "OUT_OF_SCOPE", pending: null, retrieved: [] });
  expect(screen.getByText(/no action was taken/)).toBeDefined();
  expect(screen.getByText(/No knowledge base article/)).toBeDefined();
});

it("explains a run with retrieval off", async () => {
  await triage({
    path: "NO_TOOLS",
    pending: null,
    retrieved: [],
    use_retrieval: false,
  });
  expect(screen.getByText(/the agent has no tools/)).toBeDefined();
  expect(screen.getByText(/nothing was retrieved/)).toBeDefined();
});

it("shows a failed triage", async () => {
  replies["/api/triage"] = 502;
  render(<App />);
  await screen.findByRole("button", { name: "Assistant" });
  fireEvent.change(screen.getByLabelText("Describe the issue"), {
    target: { value: "Help" },
  });
  click("Triage this ticket");
  expect((await screen.findByRole("alert")).textContent).toContain("502");
});

it("finds a run waiting at a gate after a reload", async () => {
  window.history.replaceState(null, "", "/?run=run1");
  replies["/api/runs/run1"] = baseRun;
  render(<App />);
  expect(await screen.findByRole("button", { name: "Run fix" })).toBeDefined();
});

it("forgets a run that no longer exists", async () => {
  window.history.replaceState(null, "", "/?run=gone");
  replies["/api/runs/gone"] = 404;
  render(<App />);
  await waitFor(() => {
    expect(window.location.search).toBe("");
  });
});

it("shows live statistics when opened", async () => {
  render(<App />);
  const stat = screen.getByText("Live usage statistics").closest("details");
  if (!stat) throw new Error("no statistics");
  stat.open = true;
  fireEvent(stat, new Event("toggle"));
  expect(await screen.findByText("Logged tickets")).toBeDefined();
  expect(within(stat).getByText("1.50 s")).toBeDefined();
  expect(within(stat).getByText("n/a")).toBeDefined();
  expect(within(stat).getByText(/too few for a stable rate/)).toBeDefined();
});

it("says when no statistics exist yet", async () => {
  replies["/api/stats"] = { ...stats, n: 0 };
  render(<App />);
  const stat = screen.getByText("Live usage statistics").closest("details");
  if (!stat) throw new Error("no statistics");
  stat.open = true;
  fireEvent(stat, new Event("toggle"));
  expect(await screen.findByText(/No tickets logged yet/)).toBeDefined();
});

it("says when the scoreboard has no evaluations", async () => {
  replies["/api/evaluations"] = { ...evaluations, runs: [], retrieval: [] };
  render(<App />);
  click("Scoreboard");
  expect(await screen.findByText(/No evaluations yet/)).toBeDefined();
});

it("shows retrieval scores with no evaluations, and opens another one", async () => {
  replies["/api/evaluations"] = { ...evaluations, runs: [] };
  render(<App />);
  click("Scoreboard");
  expect(await screen.findByText("unseen, development")).toBeDefined();
  expect(screen.queryByLabelText("Open an evaluation")).toBeNull();
  expect(screen.getByText("Account lockout")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Open a retrieval score"), {
    target: { value: "20261107-retrieval-unseen_dev" },
  });
  expect(screen.getByText("Certificate expiry")).toBeDefined();
  expect(screen.getByText("93%")).toBeDefined();
  expect(screen.queryByText("Account lockout")).toBeNull();
});

it("shows saved evaluations and opens another one", async () => {
  render(<App />);
  click("Scoreboard");
  expect(await screen.findByText("rules set (tiny)")).toBeDefined();
  expect(
    screen.getByText("rules set, held-out (sample, re-scored)"),
  ).toBeDefined();
  expect(screen.getByText(/CHF 120 for a wrong fix/)).toBeDefined();
  expect(screen.getByText("My VPN keeps disconnecting")).toBeDefined();
  expect(screen.getByText("Simple classifier")).toBeDefined();
  expect(screen.getByText("Agent chose")).toBeDefined();
  expect(
    screen.getByLabelText("Expected Auto-fix, chose Escalate: 1 of 4"),
  ).toBeDefined();
  expect(screen.getByText("VPN access")).toBeDefined();
  expect(screen.getAllByText("80% ±10%").length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText("Open an evaluation"), {
    target: { value: "20261103-held_out" },
  });
  expect(screen.queryByText("My VPN keeps disconnecting")).toBeNull();
});

it("shows a scoreboard failure", async () => {
  replies["/api/evaluations"] = new Error("offline");
  render(<App />);
  click("Scoreboard");
  expect(await screen.findByText("offline")).toBeDefined();
});

it("shows tickets, their first detail and the lockout count", async () => {
  render(<App />);
  click("Tickets");
  expect(await screen.findByText("2 of 2 tickets")).toBeDefined();
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(
    "My VPN keeps disconnecting",
  );
  expect(screen.getByText(/Wrong in the latest run/)).toBeDefined();
  expect(screen.getByText("2").className).toBe("wrong");
});

it("selects a ticket", async () => {
  render(<App />);
  click("Tickets");
  fireEvent.click(await screen.findByRole("button", { name: "T-002" }));
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(
    "I'm locked out",
  );
  expect(screen.getByText(/isn't in a saved evaluation/)).toBeDefined();
});

it("filters tickets", async () => {
  render(<App />);
  click("Tickets");
  await screen.findByText("2 of 2 tickets");
  click("records");
  expect(screen.getByText("1 of 2 tickets")).toBeDefined();
  click("Out of scope");
  expect(screen.getByText("No tickets match these filters.")).toBeDefined();
  click("Out of scope");
  click("records");
});

it("filters tickets by family and cause, and shows the cause", async () => {
  render(<App />);
  click("Tickets");
  await screen.findByText("2 of 2 tickets");
  fireEvent.change(screen.getByLabelText("Family"), {
    target: { value: "Account lockout" },
  });
  expect(screen.getByText("1 of 2 tickets")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Cause"), {
    target: { value: "Stale phone credentials" },
  });
  expect(screen.getByText("1 of 2 tickets")).toBeDefined();
  expect(screen.getByText("Root cause on record")).toBeDefined();
  expect(screen.getByText("account-lockout-source-check")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Family"), { target: { value: "" } });
  expect(screen.getByText("2 of 2 tickets")).toBeDefined();
});
