import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Harness } from "./Harness";
import { dnsTicket, harness, vpnTicket } from "./test-harness";

let replies: Record<string, object | number>;

beforeEach(() => {
  replies = {
    "/api/harness": harness,
    "/api/harness/tickets/INC-VDA-0001": vpnTicket,
    "/api/harness/tickets/INC-DNS-0002": dnsTicket,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const answer = replies[url];
      return Promise.resolve(
        typeof answer === "number"
          ? new Response(JSON.stringify({ detail: "The backend is down." }), {
              status: answer,
            })
          : new Response(JSON.stringify(answer)),
      );
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("draws the call as stations, from search to the person who decides", async () => {
  render(<Harness />);
  const call = await screen.findByRole("list", {
    name: "One ticket's model call, station by station",
  });
  const names = within(call)
    .getAllByRole("heading", { level: 3 })
    .map((h) => h.textContent);
  expect(names).toEqual([
    "Search code, before the model",
    "What it reads in this order",
    "One call the model",
    "The form: record_decision the model fills it in",
    "Checks on the answer code",
    "A person decides before anything runs",
  ]);
  expect(
    screen.getByText(/0.52 or more, or 0.40 and 0.15 ahead/),
  ).toBeDefined();
  expect(screen.getByText(/802 words, 2 parts/)).toBeDefined();
  expect(screen.getByText(/16, listed under/)).toBeDefined();
});

it("says plainly there's no loop, and how the model is asked", async () => {
  render(<Harness />);
  const loop = await screen.findByRole("complementary", { name: "The loop" });
  expect(loop.textContent).toContain("No loop yet. 1 call per ticket.");
  expect(
    screen.getByText(/through openrouter, pinned to alibaba/),
  ).toBeDefined();
  expect(screen.getByText(/offered but not forced/)).toBeDefined();
  expect(screen.getByText("up to 3, when the provider fails")).toBeDefined();
});

it("follows a ticket: what search found, the form filled in, and the verdict", async () => {
  render(<Harness />);
  expect(await screen.findByText("NET-VPN")).toBeDefined();
  const found = screen.getByRole("list", { name: "Found for this ticket" });
  expect(found.textContent).toContain("vpn-access");
  expect(found.textContent).toContain("0.61");
  expect(
    screen.getByText(/Wrong in full: the labels expect Auto-fix/),
  ).toBeDefined();
  expect(screen.getByText("User issue: VPN drops")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Follow a development ticket"), {
    target: { value: "INC-DNS-0002" },
  });
  expect(
    await screen.findByText(/didn't fit the form, so it went to a person/),
  ).toBeDefined();
  expect(screen.getByText("For this ticket: no clear match.")).toBeDefined();
});

it("says how to get a ticket to follow when none is saved", async () => {
  replies["/api/harness"] = { ...harness, examples: [] };
  render(<Harness />);
  expect(
    await screen.findByText(
      /No saved development run of the default model yet/,
    ),
  ).toBeDefined();
});

it("shows a failure", async () => {
  replies["/api/harness"] = 500;
  render(<Harness />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The backend is down.",
  );
});
