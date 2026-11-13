import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Benchmark } from "./benchmark";
import { Models } from "./Models";
import { benchmark, loopView } from "./test-benchmark";

let answer: Benchmark | number;

beforeEach(() => {
  answer = benchmark;
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        typeof answer === "number"
          ? new Response(JSON.stringify({ detail: "The backend is down." }), {
              status: answer,
            })
          : new Response(JSON.stringify(answer)),
      ),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const press = (name: string) => {
  fireEvent.click(screen.getByRole("button", { name }));
};

it("opens with the model the rule picks, and the rule", async () => {
  render(<Models />);
  const lede = await screen.findByRole("heading", {
    level: 2,
    name: /The rule picks/,
  });
  expect(lede.textContent).toBe(
    "The rule picks Cheap model. It saves CHF 2.00 a ticket, for CHF 1.00 per 1'000 tickets.",
  );
  expect(
    screen.getByText(
      "The owner chose Dear model as FirstLine's model instead, for how it does on unseen families, its reliability and its EU region.",
    ),
  ).toBeDefined();
  expect(
    screen.getByText(/The rule, set before the runs: the cheapest/),
  ).toBeDefined();
  expect(
    screen.getByText(/Dear model saves CHF 0.50 more a ticket/),
  ).toBeDefined();
});

it("answers questions with what the runs show", async () => {
  render(<Models />);
  expect(await screen.findByText("Which model saves the most?")).toBeDefined();
  expect(screen.getByText("Dear model, CHF 2.50 a ticket.")).toBeDefined();
});

it("plots every model with its range, the front and the free yardstick", async () => {
  render(<Models />);
  const chart = await screen.findByRole("img", { name: /3 models/ });
  expect(chart.querySelectorAll(".model")).toHaveLength(3);
  expect(chart.querySelectorAll(".model-range")).toHaveLength(3);
  expect(chart.querySelector(".front-line")).not.toBeNull();
  expect(chart.querySelector(".model-sample")).not.toBeNull();
  expect(within(chart).getByText("Classifier, free: CHF 10.72")).toBeDefined();
  expect(within(chart).getByText("Cheap model, picked")).toBeDefined();
  expect(within(chart).queryByText("Beaten model")).toBeNull();
  const beaten = chart.querySelector(".model-beaten");
  if (!beaten) throw new Error("no beaten model");
  fireEvent.mouseEnter(beaten);
  const tip = document.querySelector(".chart-tip");
  expect(tip?.textContent).toContain("Beaten model");
  expect(tip?.textContent).toContain("a sample");
  fireEvent.mouseLeave(beaten);
  expect(document.querySelector(".chart-tip")).toBeNull();
});

it("switches the chart to time", async () => {
  render(<Models />);
  await screen.findByRole("img", { name: /cost per 1'000 tickets/ });
  press("Time");
  expect(
    screen.getByRole("img", { name: /median time per ticket/ }),
  ).toBeDefined();
  expect(screen.getByText("Median time per ticket")).toBeDefined();
});

it("lists each model with who served it and every measure", async () => {
  render(<Models />);
  await screen.findByRole("img");
  const row = (name: string) => {
    const cell = screen.getByRole("rowheader", { name: new RegExp(name) });
    const tr = cell.closest("tr");
    if (!tr) throw new Error("no row");
    return within(tr);
  };
  expect(row("Dear model").getByText("mistral/eu, EU")).toBeDefined();
  expect(row("Cheap model").getByText("openai, US, effort none")).toBeDefined();
  expect(row("Cheap model").getByText("picked")).toBeDefined();
  expect(
    row("Beaten model").getByText("alibaba, region unconfirmed"),
  ).toBeDefined();
  expect(row("Beaten model").getByText("beaten")).toBeDefined();
  expect(row("Beaten model").getByText("sample")).toBeDefined();
  expect(row("Classifier").getByText("free, on this machine")).toBeDefined();
  expect(row("Classifier").getByText("the bar")).toBeDefined();
  expect(row("Cheap model").getByText("cost, time")).toBeDefined();
  expect(row("Cheap model").getByText("75% of 129")).toBeDefined();
});

it("says when a set has no runs, and how to make one", async () => {
  render(<Models />);
  await screen.findByRole("img");
  press("Families with no playbook");
  expect(screen.getByText(/No model has a run on this set yet/)).toBeDefined();
  press("Rules set");
  expect(screen.getByRole("img", { name: /1 models/ })).toBeDefined();
});

it("says when no model has a development run", async () => {
  answer = { ...benchmark, chosen: null, insights: [] };
  render(<Models />);
  expect(
    await screen.findByText(/No model has a development run yet/),
  ).toBeDefined();
  expect(screen.queryByText("What the runs show")).toBeNull();
});

it("says when no model passes the rule", async () => {
  answer = { ...benchmark, chosen: { model: null, label: null, best: "dear" } };
  render(<Models />);
  expect(
    await screen.findByText("No model passes the rule yet."),
  ).toBeDefined();
});

it("shows a failure", async () => {
  answer = 500;
  render(<Models />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The backend is down.",
  );
});

it("says how to make a loop run when there is none", async () => {
  render(<Models />);
  const section = await screen.findByRole("region", {
    name: "Does investigating pay?",
  });
  expect(within(section).getByText(/--design loop/)).toBeDefined();
});

it("draws each model's loop beside its one call, with the rule's verdict", async () => {
  answer = { ...benchmark, loop: loopView };
  render(<Models />);
  const section = await screen.findByRole("region", {
    name: "Does investigating pay?",
  });
  expect(within(section).getByText("Gemini: keep the loop")).toBeDefined();
  expect(
    within(section).getByRole("img", {
      name: /an arrow from one call to the loop/,
    }),
  ).toBeDefined();
  const row = within(section).getByRole("row", { name: /Gemini/ });
  expect(row.textContent).toContain("CHF 4.00 → CHF 6.00");
  expect(row.textContent).toContain("30 of 40");
  expect(row.textContent).toContain("96% of 50");
  fireEvent.click(within(section).getByRole("button", { name: "Rules set" }));
  expect(
    within(section).getByText("No model has a loop run on this set yet."),
  ).toBeDefined();
});
