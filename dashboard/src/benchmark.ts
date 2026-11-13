import { francs } from "./format";

/** How a run investigated, for the loop. */
export interface Investigation {
  tickets: number;
  lookups_per_ticket: number | null;
  required_checks: number;
  required_run: number;
  required_share: number | null;
  needless_per_ticket: number | null;
  citations: number;
  citations_valid: number | null;
  citations_dropped: number;
}

export interface BenchmarkEntry {
  design?: "one call" | "loop";
  investigation?: Investigation | null;
  model: string;
  label: string;
  kind: "model" | "yardstick";
  source: string;
  sample: boolean;
  serving: {
    lab: string;
    provider: string | null;
    region: string;
    effort: string | null;
  } | null;
  n: number;
  net_chf: number;
  net_low: number;
  net_high: number;
  cost_chf: number | null;
  time_p50_sec: number | null;
  time_p90_sec: number | null;
  path_accuracy: number;
  path_margin: number;
  action_accuracy: number;
  balanced_accuracy: number | null;
  mistake_cost_chf: number;
  security_mistakes: number | null;
  invalid: number;
  front_cost: boolean;
  front_time: boolean;
}

export type BenchmarkSet = "dev" | "unseen_dev" | "rules";

export interface Benchmark {
  sets: Record<BenchmarkSet, { set: BenchmarkSet; entries: BenchmarkEntry[] }>;
  rule: string;
  chosen: { model: string | null; label: string | null; best: string } | null;
  /** The model the product runs on today, which the owner sets. */
  default: { model: string; label: string };
  insights: { question: string; answer: string }[];
  catch_rate: number;
  loop: LoopView;
}

/** One model's loop run beside its own one call on the same tickets. */
export interface LoopPair {
  model: string;
  label: string;
  n: number;
  one_call: BenchmarkEntry;
  loop: BenchmarkEntry;
}

/** What the loop rule says for a model, test by test. */
export interface LoopVerdict {
  saves_more: boolean;
  safe: boolean;
  valid: boolean;
  cheap: boolean;
  keep: boolean;
  gain_chf: number;
  extra_cost_chf: number;
}

export interface LoopView {
  rule: string;
  sets: Record<BenchmarkSet, LoopPair[]>;
  verdicts: Record<string, LoopVerdict>;
}

export type Axis = "cost" | "time";

const PER = 1000; // costs read per 1'000 tickets, so they aren't all zeros

/** Where a model sits across: its cost per 1'000 tickets, or its median time. */
export function across(e: BenchmarkEntry, axis: Axis) {
  if (axis === "time") return e.time_p50_sec;
  return e.cost_chf === null ? null : e.cost_chf * PER;
}

export const perThousand = (cost: number | null) =>
  cost === null ? "unknown" : francs(cost * PER);

export interface Spot {
  x: number;
  y: number;
}

export interface LabelSpot extends Spot {
  anchor: "start" | "end";
}

const CHAR = 6.6; // the width of one character of a 12px label, near enough
const LINE = 14;

export interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

const overlaps = (a: Box, b: Box) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

function box(spot: LabelSpot, text: string): Box {
  const width = text.length * CHAR;
  const left = spot.anchor === "start" ? spot.x : spot.x - width;
  return {
    left,
    right: left + width,
    top: spot.y - LINE + 3,
    bottom: spot.y + 3,
  };
}

/** Whether a straight line from `a` to `b` passes through a box. */
function crosses(line: readonly [Spot, Spot], b: Box) {
  const [a, z] = line;
  const steps = Math.ceil(Math.hypot(z.x - a.x, z.y - a.y) / 2) || 1;
  for (let i = 0; i <= steps; i++) {
    const x = a.x + ((z.x - a.x) * i) / steps;
    const y = a.y + ((z.y - a.y) * i) / steps;
    if (x > b.left && x < b.right && y > b.top && y < b.bottom) return true;
  }
  return false;
}

/** A place for each label beside its dot: above or below, right or left, where it
 * doesn't cover another label, a dot or a line, and stays inside the plot. */
export function placeLabels(
  labels: (Spot & { text: string })[],
  dots: Spot[],
  bounds: Box,
  lines: readonly (readonly [Spot, Spot])[] = [],
): LabelSpot[] {
  const taken: Box[] = dots.map((d) => ({
    left: d.x - 6,
    right: d.x + 6,
    top: d.y - 6,
    bottom: d.y + 6,
  }));
  return labels.map((l) => {
    const options: LabelSpot[] = [
      { x: l.x + 10, y: l.y - 9, anchor: "start" },
      { x: l.x - 10, y: l.y - 9, anchor: "end" },
      { x: l.x + 10, y: l.y + 19, anchor: "start" },
      { x: l.x - 10, y: l.y + 19, anchor: "end" },
    ];
    const fits = (o: LabelSpot) => {
      const b = box(o, l.text);
      return (
        b.left >= bounds.left &&
        b.right <= bounds.right &&
        b.top >= bounds.top &&
        b.bottom <= bounds.bottom &&
        !taken.some((t) => overlaps(t, b)) &&
        !lines.some((line) => crosses(line, b))
      );
    };
    const spot = options.find(fits) ?? options[0];
    taken.push(box(spot, l.text));
    return spot;
  });
}

/** Where to label a horizontal line: at either end, above or below it, wherever the
 * label covers the fewest dots. */
export function quietSide(
  y: number,
  text: string,
  dots: Spot[],
  bounds: Pick<Box, "left" | "right">,
): LabelSpot {
  const covered = (spot: LabelSpot) => {
    const b = box(spot, text);
    return dots.filter(
      (d) =>
        d.x + 6 > b.left &&
        d.x - 6 < b.right &&
        d.y + 6 > b.top &&
        d.y - 6 < b.bottom,
    ).length;
  };
  const options: LabelSpot[] = [
    { x: bounds.left + 4, y: y - 6, anchor: "start" },
    { x: bounds.right - 4, y: y - 6, anchor: "end" },
    { x: bounds.left + 4, y: y + 16, anchor: "start" },
    { x: bounds.right - 4, y: y + 16, anchor: "end" },
  ];
  return options.reduce(
    (best, o) => (covered(o) < covered(best) ? o : best),
    options[0],
  );
}

/** Round steps between two values, for an axis. */
export function linearTicks(lo: number, hi: number) {
  const raw = (hi - lo) / 5;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
    out.push(Math.round(v * 1000) / 1000);
  }
  return out;
}
