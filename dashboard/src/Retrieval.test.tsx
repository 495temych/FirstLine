import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Retrieval } from "./Retrieval";
import { retrievalView, searches } from "./test-retrieval";

let view: object | number;
let search: object | number;
let asked: string[];

const reply = (body: object | number) =>
  typeof body === "number"
    ? new Response(JSON.stringify({ detail: "The backend is down." }), {
        status: body,
      })
    : new Response(JSON.stringify(body));

beforeEach(() => {
  view = retrievalView;
  search = searches.sure;
  asked = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (typeof init?.body === "string") asked.push(init.body);
      return Promise.resolve(
        reply(url === "/api/retrieval/search" ? search : view),
      );
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const panel = () => screen.getByRole("complementary", { name: "Ticket" });

async function searchFor(text: string) {
  fireEvent.change(
    await screen.findByLabelText("A request, as someone would write it"),
    { target: { value: text } },
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Search the knowledge base, free" }),
  );
}

it("opens with what search finds, on both kinds of family", async () => {
  render(<Retrieval />);
  expect(
    await screen.findByRole("heading", {
      name: "Search finds the right playbook for 1 of 2 development tickets.",
    }),
  ).toBeTruthy();
  expect(screen.getByText(/For 1 of 2 tickets from families/)).toBeTruthy();
});

it("explains the bar with the gap the scores leave", async () => {
  render(<Retrieval />);
  expect(
    await screen.findByText(/weakest right match scores 0.45/),
  ).toBeTruthy();
  expect(screen.getByText(/1 of those clear the 0.52 bar/)).toBeTruthy();
});

it("opens a wrong ticket first, and any other from the chart or table", async () => {
  render(<Retrieval />);
  expect((await screen.findByLabelText("Ticket")).textContent).toContain(
    "It found wifi instead of vpn-access.",
  );
  fireEvent.click(screen.getByText("The 4 tickets as a table"));
  fireEvent.click(screen.getByRole("button", { name: "INC-VDA-0001" }));
  expect(panel().textContent).toContain("It found vpn-access, its family's");
  expect(panel().textContent).toContain("sec-04 (policy, 0.38)");
  expect(within(panel()).getByText("(should match)")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "INC-CES-0002" }));
  expect(panel().textContent).toContain("though this family has no playbook");
  fireEvent.click(screen.getByRole("button", { name: "INC-CES-0003" }));
  expect(panel().textContent).toContain("as it should");
});

it("shows a ticket's scores on hover and opens it on click", async () => {
  const { container } = render(<Retrieval />);
  await screen.findByLabelText("Ticket");
  const dots = container.querySelectorAll(".dot");
  expect(dots).toHaveLength(3);
  fireEvent.mouseEnter(dots[0]);
  expect(screen.getByRole("status").textContent).toContain("0.70 against 0.40");
  fireEvent.mouseLeave(dots[0]);
  expect(screen.queryByRole("status")).toBeNull();
  fireEvent.click(dots[0]);
  expect(panel().textContent).toContain("VPN drops at home");
});

it("says when a covered ticket found nothing", async () => {
  const dev = retrievalView.sets.dev;
  if (!dev) throw new Error("The fixture has a development set.");
  view = {
    ...retrievalView,
    sets: {
      ...retrievalView.sets,
      dev: { ...dev, tickets: [{ ...dev.tickets[1], top: null }] },
    },
  };
  render(<Retrieval />);
  expect((await screen.findByLabelText("Ticket")).textContent).toContain(
    "It found nothing, though vpn-access should match.",
  );
});

it("lists each measure with its question, n, floor and history", async () => {
  render(<Retrieval />);
  const hit = (await screen.findByRole("rowheader", { name: "Hit rate" }))
    .parentElement;
  expect(hit?.textContent).toContain("95%, or the check fails");
  expect(hit?.textContent).toContain("94% → 50%");
  const rank = screen.getByRole("rowheader", {
    name: "Reciprocal rank",
  }).parentElement;
  expect(rank?.textContent).toContain("None yet");
  expect(rank?.textContent).toContain("75% in the 1 saved scores");
  const falseMatch = screen.getByRole("rowheader", {
    name: "False matches",
  }).parentElement;
  expect(falseMatch?.textContent).toContain("50%");
  expect(screen.getByText("Certificate expiry")).toBeTruthy();
});

it("runs a search and says why a playbook matched", async () => {
  render(<Retrieval />);
  await searchFor("VPN drops");
  expect(
    await screen.findByText(/It matches doc-0: 0.60 clears the 0.52 bar/),
  ).toBeTruthy();
  expect(asked).toEqual([JSON.stringify({ text: "VPN drops" })]);
  expect(screen.getByText("Reset the VPN profile.")).toBeTruthy();
});

it.each([
  ["clear", /0.45 is above 0.40 and 0.20 ahead/],
  ["low", /No playbook matches: the best, doc-0, scores 0.30, under 0.40/],
  ["close", /only 0.05 ahead of the next, short of 0.15/],
  ["empty", /The knowledge base is empty/],
])("explains a %s search", async (kind, sentence) => {
  search = searches[kind];
  render(<Retrieval />);
  await searchFor("something");
  expect(await screen.findByText(sentence)).toBeTruthy();
});

it("shows why a search failed", async () => {
  search = 503;
  render(<Retrieval />);
  await searchFor("VPN");
  expect((await screen.findByRole("alert")).textContent).toContain(
    "The backend is down.",
  );
});

it("is honest that the decision without search isn't measured", async () => {
  render(<Retrieval />);
  expect(await screen.findByText(/73%, give or take 8%, on 129/)).toBeTruthy();
  expect(screen.getByText(/Not measured yet/).textContent).toContain(
    "CHF 0.65",
  );
});

it("shows both decisions once both are saved", async () => {
  const on = retrievalView.decision.with_search;
  view = {
    ...retrievalView,
    decision: { with_search: null, without_search: on },
  };
  render(<Retrieval />);
  expect(await screen.findByText(/No development run is saved/)).toBeTruthy();
  expect(screen.getByText(/73%, give or take 8%/)).toBeTruthy();
});

it("says how to save a score when none has its tickets", async () => {
  view = { ...retrievalView, sets: { dev: null, unseen_dev: null } };
  render(<Retrieval />);
  expect(await screen.findByText(/No retrieval score/)).toBeTruthy();
});

it("shows an error when the scores can't load", async () => {
  view = 503;
  render(<Retrieval />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "The backend is down.",
  );
});
