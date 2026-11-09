import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BusinessCase } from "./BusinessCase";
import { business, losing } from "./test-business";

let answer: object | number;
let asked: string[];

beforeEach(() => {
  answer = business;
  asked = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      asked.push(url);
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
  vi.useRealTimers();
});

const row = (name: string) =>
  screen.getByRole("rowheader", { name }).parentElement?.textContent;

it("opens with the net saving and what it rests on", async () => {
  render(<BusinessCase />);
  expect(
    await screen.findByRole("heading", {
      name: "Each ticket saves CHF 0.97 net, about CHF 1'458 a year.",
    }),
  ).toBeTruthy();
  expect(screen.getByText(/It pays only above 89%/)).toBeTruthy();
  expect(screen.getByText(/they caught 0 of 9/)).toBeTruthy();
});

it("lays projected and observed side by side", async () => {
  render(<BusinessCase />);
  await screen.findByRole("heading", { name: /Each ticket saves/ });
  expect(row("Review time per ticket")).toContain("2.0 min, assumed");
  expect(row("Review time per ticket")).toContain("1:19, measured");
  expect(row("Mistakes caught")).toContain("0%, measured");
  expect(row("Its range, from the margin")).toContain("CHF -0.19 to CHF 2.13");
  expect(row("Share caught it needs")).toContain("80%");
  expect(screen.getByText(/129 labelled tickets/)).toBeTruthy();
  expect(screen.getByText("20261108T010442-dev-rescored")).toBeTruthy();
});

it("says when it loses money, and when it can't pay at all", async () => {
  answer = losing;
  render(<BusinessCase />);
  expect(
    await screen.findByRole("heading", {
      name: "Each ticket loses CHF 5.00 net, about CHF 7'500 a year.",
    }),
  ).toBeTruthy();
  expect(row("Share caught it needs")).toContain(
    "Can't pay, even catching all",
  );
  expect(row("Approved unchanged")).toContain("n/a");
  expect(screen.getByText(/no reviews yet/)).toBeTruthy();
});

it("says when there are no mistakes to catch", async () => {
  answer = {
    ...business,
    observed: business.observed && {
      ...business.observed,
      catch_needed: null,
      wrong: 0,
    },
  };
  render(<BusinessCase />);
  await screen.findByRole("heading", { name: /Each ticket saves/ });
  expect(row("Share caught it needs")).toContain("No mistakes to catch");
});

it("asks again when the reader moves an assumption", async () => {
  render(<BusinessCase />);
  await screen.findByRole("heading", { name: /Each ticket saves/ });
  vi.useFakeTimers();
  fireEvent.change(
    screen.getByRole("slider", { name: /A first pass by hand takes/ }),
    {
      target: { value: "10" },
    },
  );
  fireEvent.change(screen.getByRole("slider", { name: /A technician costs/ }), {
    target: { value: "80" },
  });
  fireEvent.change(screen.getByRole("slider", { name: /Technicians catch/ }), {
    target: { value: "0.95" },
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(200);
  });
  expect(asked.at(-1)).toBe(
    "/api/business?minutes_by_hand=10&chf_per_hour=80&catch_rate=0.95",
  );
});

it("draws both lines and reads them on hover", async () => {
  const { container } = render(<BusinessCase />);
  await screen.findByRole("heading", { name: /Each ticket saves/ });
  const svg = container.querySelector("svg");
  if (!svg) throw new Error("The chart has an svg.");
  expect(within(container).getByText("Projected, 90% caught")).toBeTruthy();
  expect(within(container).getByText("Observed, 0% caught")).toBeTruthy();
  svg.getBoundingClientRect = () => new DOMRect(0, 0, 640, 320);
  fireEvent.mouseMove(svg, { clientX: 64 + 552, clientY: 100 });
  const tip = () => container.querySelector(".chart-tip");
  expect(tip()?.textContent).toContain("100% caught");
  expect(tip()?.textContent).toContain("Projected: CHF 8.69");
  fireEvent.mouseMove(svg, { clientX: 10, clientY: 100 });
  expect(tip()).toBeNull();
  fireEvent.mouseMove(svg, { clientX: 64, clientY: 100 });
  fireEvent.mouseLeave(svg);
  expect(tip()).toBeNull();
});

it("says how to project when no evaluation is saved", async () => {
  answer = { ...business, projected: null, observed: null };
  const { container } = render(<BusinessCase />);
  expect(await screen.findByText(/nothing to project/)).toBeTruthy();
  expect(container.querySelector("svg")).toBeNull();
});

it("shows an error when the case can't load", async () => {
  answer = 503;
  render(<BusinessCase />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "The backend is down.",
  );
});
