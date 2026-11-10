import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Queue } from "./Queue";
import {
  busyQueue,
  closedTicket,
  emptyQueue,
  escalationTicket,
  queueTicket,
  readyTrace,
} from "./test-data";

type Reply = object | number;

let replies: Partial<Record<string, Reply>>;
const calls: { url: string; body: unknown }[] = [];

const TRACE = `/api/queue/tickets/${queueTicket.id}/trace`;
const REVIEW = `/api/queue/tickets/${queueTicket.id}/review`;

function reply(url: string, init?: RequestInit) {
  const body = init?.body ? (JSON.parse(init.body as string) as unknown) : null;
  calls.push({ url, body });
  const answer = replies[url];
  if (typeof answer === "number") {
    const detail = JSON.stringify({ detail: "Say why the decision is wrong." });
    return Promise.resolve(new Response(detail, { status: answer }));
  }
  return Promise.resolve(new Response(JSON.stringify(answer ?? {})));
}

beforeEach(() => {
  calls.length = 0;
  replies = {
    "/api/queue": busyQueue,
    "/api/queue/load": busyQueue,
    [TRACE]: readyTrace,
    [`/api/queue/tickets/${escalationTicket.id}/trace`]: readyTrace,
  };
  vi.stubGlobal("fetch", vi.fn(reply));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const click = (name: string | RegExp) => {
  fireEvent.click(screen.getByRole("button", { name }));
};

/** Opens a ticket's card by its title. */
const pick = (title: string) => {
  fireEvent.click(screen.getByText(title, { selector: ".card-title" }));
};

async function open(title: string) {
  render(<Queue />);
  await screen.findByText(title);
  pick(title);
}

it("starts empty and loads a batch from the service desk", async () => {
  replies["/api/queue"] = emptyQueue;
  render(<Queue />);
  expect(await screen.findByText(/The board is empty/)).toBeDefined();
  expect(screen.getByText("129 waiting at the desk")).toBeDefined();
  click("Load 8 tickets from the service desk");
  expect(await screen.findByText(queueTicket.title)).toBeDefined();
  expect(calls.some((c) => c.url === "/api/queue/load")).toBe(true);
});

it("puts each ticket in the column of its state, with a count", async () => {
  render(<Queue />);
  const column = async (name: string) =>
    within(await screen.findByRole("list", { name }));
  expect(
    (await column("Waiting for a technician, 2 tickets")).getAllByRole(
      "button",
    ),
  ).toHaveLength(2);
  expect(
    (await column("Queued, 1 tickets")).getByText(
      "Printer on floor 3 is jammed",
    ),
  ).toBeDefined();
  expect(
    (await column("Agent working, 0 tickets")).queryAllByRole("button"),
  ).toHaveLength(0);
  expect(
    (await column("Closed, 1 tickets")).getByText("VPN certificate expired"),
  ).toBeDefined();
  expect(
    (await column("Failed, 1 tickets")).getByText("Needs a person"),
  ).toBeDefined();
});

it("shows the latest closed tickets, and the rest on request", async () => {
  const closed = Array.from({ length: 8 }, (_, i) => ({
    ...closedTicket,
    id: `INC-CLS-${i.toString()}`,
    title: `Closed ticket ${i.toString()}`,
    review: closedTicket.review && {
      ...closedTicket.review,
      at: `2026-11-10T09:0${i.toString()}:00Z`,
    },
  }));
  replies["/api/queue"] = { ...busyQueue, tickets: closed };
  render(<Queue />);
  expect(await screen.findByText("Closed ticket 7")).toBeDefined();
  expect(screen.queryByText("Closed ticket 1")).toBeNull();
  click("Show 2 more");
  expect(screen.getByText("Closed ticket 1")).toBeDefined();
  click("Show the latest only");
  expect(screen.queryByText("Closed ticket 1")).toBeNull();
});

it("shows how the batch went, and sends the money to its own view", async () => {
  render(<Queue />);
  const value = await screen.findByRole("region", {
    name: "How the batch went",
  });
  expect(within(value).getByText("0 of 1")).toBeDefined();
  expect(within(value).getByText("1:15")).toBeDefined();
  expect(within(value).getByText("CHF 0.0144")).toBeDefined();
  expect(
    within(value).getByText(/is under Is it worth it\?, Money/),
  ).toBeDefined();
});

it("labels each ticket with its status and the agent's decision", async () => {
  render(<Queue />);
  await screen.findByText(queueTicket.title);
  expect(screen.getByText("Rerouted")).toBeDefined();
  expect(screen.getAllByText("reset_vpn_profile").length).toBeGreaterThan(0);
  expect(screen.getByText("SEC-INCIDENT")).toBeDefined();
  const card = screen.getByRole("button", { name: /VPN drops every few/ });
  expect(card.className).toContain("path-AUTO_FIX");
});

it("asks for a ticket to be chosen, and closes the drawer", async () => {
  await open(queueTicket.title);
  expect(screen.queryByText(/Choose a ticket/)).toBeNull();
  click("Close");
  expect(screen.queryByRole("complementary", { name: "Ticket" })).toBeNull();
  expect(screen.getByText(/Choose a ticket/)).toBeDefined();
});

it("shows a ticket's evidence, reasoning and proposal", async () => {
  await open(queueTicket.title);
  const detail = screen.getByRole("complementary", { name: "Ticket" });
  expect(within(detail).getByText("vpn-access, Fix")).toBeDefined();
  expect(
    within(detail).getByText("Likely cause: Stale VPN profile"),
  ).toBeDefined();
  expect(within(detail).getByText("migration")).toBeDefined();
  expect(within(detail).getByText("username")).toBeDefined();
  expect(within(detail).getByText(/Anna Berg, Finance, Zurich/)).toBeDefined();
});

it("shows the ticket's trace from Langfuse", async () => {
  await open(queueTicket.title);
  expect(await screen.findByText("Search the knowledge base")).toBeDefined();
  expect(screen.getByText("Model call")).toBeDefined();
  expect(screen.getByText(/3’564 tokens in|3'564 tokens in/)).toBeDefined();
  const link = screen.getByRole("link", { name: /Open the full trace/ });
  expect(link.getAttribute("href")).toBe(readyTrace.url);
});

it("says when tracing is off or the trace hasn't arrived", async () => {
  replies[TRACE] = { status: "off", url: null, steps: [] };
  await open(queueTicket.title);
  expect(await screen.findByText(/Tracing is off/)).toBeDefined();
  cleanup();
  replies[TRACE] = { status: "pending", url: readyTrace.url, steps: [] };
  await open(queueTicket.title);
  expect(await screen.findByText(/Waiting for Langfuse/)).toBeDefined();
});

it("approves a fix, times the decision and moves to the next ticket", async () => {
  replies[REVIEW] = { ...queueTicket, state: "closed" };
  await open(queueTicket.title);
  replies["/api/queue"] = {
    ...busyQueue,
    tickets: busyQueue.tickets.filter((t) => t.id !== queueTicket.id),
  };
  click("Approve and run fix");
  expect(
    await screen.findByRole("button", {
      name: "Approve and send to SEC-INCIDENT",
    }),
  ).toBeDefined();
  const sent = calls.find((c) => c.url === REVIEW)?.body as {
    verdict: string;
    seconds: number;
  };
  expect(sent.verdict).toBe("approved");
  expect(sent.seconds).toBeGreaterThanOrEqual(0);
});

it("sends a ticket to another team", async () => {
  replies[REVIEW] = { ...queueTicket, state: "closed" };
  await open(queueTicket.title);
  const send = screen.getByRole("button", { name: "Send to team" });
  expect((send as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Team"), {
    target: { value: "NET-VPN" },
  });
  click("Send to team");
  await waitFor(() => {
    expect(calls.find((c) => c.url === REVIEW)?.body).toMatchObject({
      verdict: "corrected",
      queue: "NET-VPN",
    });
  });
});

it("rejects a decision only with a reason, and shows a refusal", async () => {
  replies[REVIEW] = 422;
  await open(queueTicket.title);
  const reject = screen.getByRole("button", {
    name: "Reject and handle by hand",
  });
  expect((reject as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Why is it wrong?"), {
    target: { value: "Wrong user" },
  });
  click("Reject and handle by hand");
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Say why the decision is wrong.",
  );
  expect(calls.find((c) => c.url === REVIEW)?.body).toMatchObject({
    verdict: "rejected",
    note: "Wrong user",
  });
});

it("shows what happened to a closed ticket", async () => {
  await open("VPN certificate expired");
  expect(screen.getByText("Rerouted to NET-VPN")).toBeDefined();
  expect(screen.getByText(/Ticket #INC1234567 opened/)).toBeDefined();
  expect(screen.getByText(/Decided in 1:15/)).toBeDefined();
});

it("shows a queued ticket and a failed one", async () => {
  await open("Printer on floor 3 is jammed");
  expect(screen.getByText(/The agent will pick it up next/)).toBeDefined();
  pick("Wi-Fi keeps dropping");
  expect(screen.getByRole("alert").textContent).toContain(
    "RuntimeError: model unavailable",
  );
});

it("keeps reading the board while the agent works", async () => {
  render(<Queue />);
  await screen.findByText(queueTicket.title);
  await waitFor(
    () => {
      expect(calls.filter((c) => c.url === "/api/queue")).toHaveLength(2);
    },
    { timeout: 2500 },
  );
});

it("shows a board that can't be read", async () => {
  replies["/api/queue"] = 500;
  render(<Queue />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Say why the decision is wrong.",
  );
});
