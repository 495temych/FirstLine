import { expect, it } from "vitest";
import { placeLabels, quietSide } from "./benchmark";

const bounds = { left: 0, right: 400, top: 0, bottom: 300 };

it("puts a label above and to the right when there's room", () => {
  const [spot] = placeLabels([{ x: 50, y: 100, text: "Model" }], [], bounds);
  expect(spot).toEqual({ x: 60, y: 91, anchor: "start" });
});

it("moves a label that would cover another one", () => {
  const spots = placeLabels(
    [
      { x: 50, y: 100, text: "A long first label" },
      { x: 70, y: 100, text: "Second" },
    ],
    [],
    bounds,
  );
  expect(spots[1]).not.toEqual({ x: 80, y: 91, anchor: "start" });
});

it("keeps a label near the right edge inside the plot", () => {
  const [spot] = placeLabels([{ x: 390, y: 100, text: "Edge" }], [], bounds);
  expect(spot.anchor).toBe("end");
});

it("moves a label off a line drawn through it", () => {
  const line = [
    { x: 0, y: 88 },
    { x: 400, y: 88 },
  ] as const;
  const [spot] = placeLabels([{ x: 50, y: 100, text: "Model" }], [], bounds, [
    line,
  ]);
  expect(spot.y).toBeGreaterThan(100);
});

it("labels a line where the label covers no dot", () => {
  const at = (dots: { x: number; y: number }[]) =>
    quietSide(100, "Yardstick", dots, bounds);
  expect(at([{ x: 380, y: 92 }])).toMatchObject({ anchor: "start", y: 94 });
  expect(at([{ x: 20, y: 92 }])).toMatchObject({ anchor: "end", y: 94 });
  expect(
    at([
      { x: 20, y: 92 },
      { x: 380, y: 92 },
    ]),
  ).toMatchObject({ y: 116 });
});
