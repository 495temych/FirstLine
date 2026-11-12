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
import { benchmark } from "./test-benchmark";
import { harness, vpnTicket } from "./test-harness";
import { overview } from "./test-overview";
import {
  baseRun,
  declined,
  draft,
  emptyQueue,
  evaluations,
  examples,
  requesters,
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
    "/api/health": {
      status: "ok",
      api_key: true,
      model: "Gemini 3.1 Flash-Lite",
    },
    "/api/triage": baseRun,
    "/api/requesters": requesters,
    "/api/examples": examples,
    "/api/evaluations": evaluations,
    "/api/tickets": tickets,
    "/api/stats": stats,
    "/api/queue": emptyQueue,
    "/api/benchmark": benchmark,
    "/api/overview": overview,
    "/api/harness": harness,
    [`/api/harness/tickets/${vpnTicket.id}`]: vpnTicket,
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

/** Opens a view through its link in the sidebar. */
const open = (name: string) => {
  fireEvent.click(screen.getByRole("link", { name }));
};

/** The Queue opens first, so the Assistant needs its tab. */
function showAssistant() {
  render(<App />);
  open("Assistant");
}

async function triage(run: Partial<Run> = {}) {
  replies["/api/triage"] = { ...baseRun, ...run };
  showAssistant();
  await screen.findByLabelText("Who is asking");
  fireEvent.change(screen.getByLabelText("Describe the issue"), {
    target: { value: "My VPN fails" },
  });
  click("Triage this ticket");
  await screen.findByText("My VPN fails", { selector: ".query" });
}

it("opens on the Queue, with every group and view in the sidebar", async () => {
  render(<App />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Queue" }),
  ).toBeDefined();
  const sidebar = screen.getByRole("navigation", { name: "Views" });
  for (const group of ["Try it", "Is it worth it?", "How it works"]) {
    expect(within(sidebar).getByRole("list", { name: group })).toBeDefined();
  }
  expect(within(sidebar).getAllByRole("link")).toHaveLength(9);
  expect(
    within(sidebar)
      .getByRole("link", { name: "Queue" })
      .getAttribute("aria-current"),
  ).toBe("page");
  expect(await screen.findByText(/The board is empty/)).toBeDefined();
  expect(await screen.findByText("Gemini 3.1 Flash-Lite")).toBeDefined();
});

it("gives every view its own link, and follows back and forward", async () => {
  render(<App />);
  open("Money");
  expect(window.location.search).toBe("?view=money");
  open("Models");
  expect(window.location.search).toBe("?view=models");
  expect(
    screen.getByRole("link", { name: "Models" }).getAttribute("href"),
  ).toBe("?view=models");
  window.history.pushState(null, "", "?view=tickets");
  fireEvent(window, new PopStateEvent("popstate"));
  expect(await screen.findByText("2 of 2 tickets")).toBeDefined();
});

it("opens the view a shared link names", async () => {
  window.history.replaceState(null, "", "/?view=evaluations");
  render(<App />);
  expect(await screen.findByText("rules set (tiny)")).toBeDefined();
  expect(
    screen
      .getByRole("link", { name: "Evaluations" })
      .getAttribute("aria-current"),
  ).toBe("page");
});

it("opens the Queue for a link to a view that doesn't exist", () => {
  window.history.replaceState(null, "", "/?view=nowhere");
  render(<App />);
  expect(
    screen.getByRole("link", { name: "Queue" }).getAttribute("aria-current"),
  ).toBe("page");
});

it("explains the harness under How it works", async () => {
  render(<App />);
  open("Harness");
  expect(window.location.search).toBe("?view=harness");
  expect(
    await screen.findByRole("list", {
      name: "One ticket's model call, station by station",
    }),
  ).toBeDefined();
  expect(
    await screen.findByRole("list", { name: "Found for this ticket" }),
  ).toBeDefined();
});

it("keeps a modified click for the browser to open in a new tab", () => {
  render(<App />);
  fireEvent.click(screen.getByRole("link", { name: "Harness" }), {
    metaKey: true,
  });
  expect(window.location.search).toBe("");
});

it("shows the example tickets on the Assistant", () => {
  showAssistant();
  expect(
    within(screen.getByRole("main")).getAllByRole("listitem"),
  ).toHaveLength(presets.length);
});

it("fills the ticket from an example without running it", () => {
  showAssistant();
  click(presets[1] ?? "");
  const box: HTMLTextAreaElement = screen.getByLabelText("Describe the issue");
  expect(box.value).toBe(presets[1]);
  expect(calls.some((c) => c.url === "/api/triage")).toBe(false);
});

it("sends the retrieval switch with the ticket", async () => {
  showAssistant();
  await screen.findByLabelText("Who is asking");
  fireEvent.click(screen.getByRole("switch"));
  fireEvent.change(screen.getByLabelText("Describe the issue"), {
    target: { value: "Help" },
  });
  click("Triage this ticket");
  await waitFor(() => {
    expect(calls.find((c) => c.url === "/api/triage")?.body).toEqual({
      text: "Help",
      use_retrieval: false,
      requester: "s.keller",
    });
  });
});

it("sends the requester picked, and shows their record", async () => {
  showAssistant();
  const picker: HTMLSelectElement =
    await screen.findByLabelText("Who is asking");
  expect(
    screen.getByText(/2 lockouts in 24 hours in the records/),
  ).toBeDefined();
  fireEvent.change(picker, { target: { value: "m.huber" } });
  expect(
    screen.getByText(/1 lockout in 24 hours in the records/),
  ).toBeDefined();
  fireEvent.change(screen.getByLabelText("Describe the issue"), {
    target: { value: "Locked out" },
  });
  click("Triage this ticket");
  await waitFor(() => {
    expect(calls.find((c) => c.url === "/api/triage")?.body).toEqual({
      text: "Locked out",
      use_retrieval: true,
      requester: "m.huber",
    });
  });
});

it("shows when a rule changed the agent's decision", async () => {
  await triage({
    path: "ESCALATE",
    tool_name: "create_escalation_ticket",
    tool_input: { queue: "SEC-INCIDENT", summary: "s", priority: "P2-High" },
    pending: { kind: "confirm_ticket", ticket: draft },
    rule: {
      rule: "SEC-04",
      reason: "2 lockouts in 24 hours in the records.",
      code: "sec04 in agent/rules.py",
      proposed: {
        path: "AUTO_FIX",
        tool_name: "unlock_ad_account",
        tool_input: { username: "s.keller" },
      },
    },
  });
  const note = screen.getByRole("note");
  expect(note.textContent).toContain("Changed by a rule: SEC-04.");
  expect(note.textContent).toContain("Auto-fix, unlock_ad_account");
  expect(note.textContent).toContain("sec04 in agent/rules.py");
});

it("reads a working run every second until it waits at a gate", async () => {
  replies["/api/runs/run1"] = baseRun;
  await triage({
    status: "running",
    path: "",
    pending: null,
    steps: [],
    next: ["investigate"],
  });
  expect(screen.getByText("Choose the next step")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run fix" })).toBeNull();
  expect(
    await screen.findByRole("button", { name: "Run fix" }, { timeout: 3000 }),
  ).toBeDefined();
  expect(calls.some((c) => c.url === "/api/runs/run1")).toBe(true);
});

it("sends a real example with its requester and ticket id", async () => {
  showAssistant();
  fireEvent.click(
    await screen.findByRole("button", {
      name: "account locked after password change",
    }),
  );
  const picker: HTMLSelectElement = screen.getByLabelText("Who is asking");
  expect(picker.value).toBe("m.huber");
  click("Triage this ticket");
  await waitFor(() => {
    expect(calls.find((c) => c.url === "/api/triage")?.body).toEqual({
      text: "account locked after password change\n\nI changed my password.",
      use_retrieval: true,
      requester: "m.huber",
      ticket_id: "INC-ALP-0010",
    });
  });
});

it("blocks triage and explains when the key is missing", async () => {
  replies["/api/health"] = { status: "ok", api_key: false };
  showAssistant();
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
  expect(
    screen.getByText("Auto-fix", { selector: ".path-name" }),
  ).toBeDefined();
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
  expect(window.location.search).toBe("?view=assistant&run=run1");
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
  showAssistant();
  await screen.findByLabelText("Who is asking");
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
  replies["/api/evaluations"] = { ...evaluations, runs: [] };
  render(<App />);
  open("Evaluations");
  expect(await screen.findByText(/No evaluations yet/)).toBeDefined();
});

it("shows saved evaluations and opens another one", async () => {
  render(<App />);
  open("Evaluations");
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
  open("Evaluations");
  expect(await screen.findByText("offline")).toBeDefined();
});

it("shows tickets, their first detail and the lockout count", async () => {
  render(<App />);
  open("Tickets");
  expect(await screen.findByText("2 of 2 tickets")).toBeDefined();
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(
    "My VPN keeps disconnecting",
  );
  expect(screen.getByText(/Wrong in the latest run/)).toBeDefined();
  expect(screen.getByText("2").className).toBe("wrong");
});

it("selects a ticket", async () => {
  render(<App />);
  open("Tickets");
  fireEvent.click(await screen.findByRole("button", { name: "T-002" }));
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(
    "I'm locked out",
  );
  expect(screen.getByText(/isn't in a saved evaluation/)).toBeDefined();
});

it("filters tickets", async () => {
  render(<App />);
  open("Tickets");
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
  open("Tickets");
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
