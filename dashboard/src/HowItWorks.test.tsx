import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { HowItWorks } from "./HowItWorks";
import { overview } from "./test-overview";

let reply: object | number;

beforeEach(() => {
  reply = overview;
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        typeof reply === "number"
          ? new Response(JSON.stringify({ detail: "The backend is down." }), {
              status: reply,
            })
          : new Response(JSON.stringify(reply)),
      ),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const station = (name: string) => screen.getAllByRole("button", { name })[0];
const panel = () => screen.getByRole("complementary", { name: "Station" });

it("opens with the goal and explains the decision station", async () => {
  render(<HowItWorks />);
  expect(
    await screen.findByRole("heading", {
      name: "Every ticket gets a correct first pass.",
    }),
  ).toBeTruthy();
  expect(station("Decide").getAttribute("aria-pressed")).toBe("true");
  expect(panel().textContent).toContain("Decide does its job.");
  expect(panel().textContent).toContain(
    "It found the likely cause, stale check-in",
  );
  expect(panel().textContent).toContain("INC-DCP-0004");
});

it("marks the stations where a person decides", async () => {
  render(<HowItWorks />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Approve the fix/ }),
  );
  expect(panel().textContent).toContain("A person decides here.");
  expect(panel().textContent).toContain("The fix is force_intune_sync.");
  expect(screen.getAllByText("(a person decides)").length).toBeGreaterThan(0);
});

it("follows another path, keeping only stations on its route", async () => {
  render(<HowItWorks />);
  fireEvent.click(await screen.findByRole("button", { name: "Run the fix" }));
  fireEvent.click(screen.getByLabelText("Escalate"));
  expect(panel().textContent).toContain("Decide does its job.");
  fireEvent.click(
    screen.getAllByRole("button", { name: /Approve the ticket/ })[1],
  );
  expect(panel().textContent).toContain("The ticket goes to SEC-INCIDENT.");
});

it("says when a path has no example to follow", async () => {
  render(<HowItWorks />);
  fireEvent.click(await screen.findByLabelText("Out of scope"));
  expect(
    screen.getByText(/no correctly handled ticket on this path/),
  ).toBeTruthy();
});

it("explains where a ticket starts and what search found", async () => {
  render(<HowItWorks />);
  fireEvent.click(
    await screen.findByRole("button", { name: "A ticket arrives" }),
  );
  expect(panel().textContent).toContain('"Device marked noncompliant"');
  fireEvent.click(station("Search the knowledge base"));
  expect(panel().textContent).toContain("It matched device-compliance.");
  fireEvent.click(screen.getByLabelText("Escalate"));
  expect(panel().textContent).toContain("Nothing matched well enough");
});

it("shows how sure we are, honestly, with its source", async () => {
  render(<HowItWorks />);
  expect(
    await screen.findByText(/73%, give or take 8 points, on 129/),
  ).toBeTruthy();
  expect(screen.getByText(/Not yet\. A simple classifier/)).toBeTruthy();
  expect(screen.getByText(/more than 13% of/)).toBeTruthy();
  expect(screen.getByText("20261108T010442-dev-rescored")).toBeTruthy();
});

it("says how to measure it when no run is saved", async () => {
  reply = { ...overview, result: null };
  render(<HowItWorks />);
  expect(await screen.findByText(/No evaluation is saved yet/)).toBeTruthy();
});

it("lists the model, tools by risk, services and limits", async () => {
  render(<HowItWorks />);
  expect(await screen.findByText("claude-haiku-4-5-20251001")).toBeTruthy();
  expect(screen.getByText(/USD 1\.00 in and USD 5\.00 out/)).toBeTruthy();
  expect(screen.getByText(/Routine, 1 tools/)).toBeTruthy();
  expect(screen.getByText(/Sensitive, 2 tools/)).toBeTruthy();
  expect(screen.getAllByText("service desk")).toHaveLength(2);
  expect(screen.getByText(/It changes no system/)).toBeTruthy();
  expect(screen.getByText("Any team")).toBeTruthy();
  expect(screen.getByText("Not set up, memory instead")).toBeTruthy();
  expect(screen.getByText("The knowledge base is synthetic.")).toBeTruthy();
});

it("says when the model has no price", async () => {
  reply = {
    ...overview,
    model: { ...overview.model, input_usd_per_million: null },
  };
  render(<HowItWorks />);
  expect(await screen.findByText(/No price on record/)).toBeTruthy();
});

it("shows an error when the overview can't load", async () => {
  reply = 503;
  render(<HowItWorks />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "The backend is down.",
  );
});
