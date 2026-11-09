import { useState } from "react";
import {
  across,
  perThousand,
  placeLabels,
  quietSide,
  type Axis,
  type Box,
  type BenchmarkEntry,
} from "./benchmark";
import { francs, percent, seconds } from "./format";

const W = 640;
const H = 380;
const PAD = { left: 60, right: 24, top: 28, bottom: 44 };

function logTicks(lo: number, hi: number) {
  const out: number[] = [];
  for (
    let p = Math.floor(Math.log10(lo));
    p <= Math.ceil(Math.log10(hi));
    p++
  ) {
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** p;
      if (v >= lo && v <= hi) out.push(v);
    }
  }
  return out;
}

function linearTicks(lo: number, hi: number) {
  const raw = (hi - lo) / 5;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
    out.push(Math.round(v * 1000) / 1000);
  }
  return out;
}

const tickLabel = (v: number, axis: Axis) =>
  axis === "cost"
    ? v.toLocaleString("de-CH", { maximumFractionDigits: 2 })
    : `${v.toLocaleString("de-CH")} s`;

interface Placed {
  e: BenchmarkEntry;
  x: number;
  y: number;
}

function ModelTip({ at }: Readonly<{ at: Placed }>) {
  const e = at.e;
  return (
    <div
      className="chart-tip"
      style={{
        left: `${((at.x / W) * 100).toFixed(1)}%`,
        top: `${((at.y / H) * 100).toFixed(1)}%`,
      }}
      role="status"
    >
      <strong>{e.label}</strong>
      <span>
        Saves {francs(e.net_chf)} a ticket, from {francs(e.net_low)} to{" "}
        {francs(e.net_high)}
      </span>
      <span>
        {perThousand(e.cost_chf)} per 1&apos;000 tickets, median{" "}
        {seconds(e.time_p50_sec)}
      </span>
      <span>
        Right in full on {percent(e.action_accuracy)} of {e.n.toString()}
        {e.sample ? ", a sample" : ""}
      </span>
    </div>
  );
}

function Yardstick({
  text,
  y,
  dots,
  bounds,
}: Readonly<{ text: string; y: number; dots: Placed[]; bounds: Box }>) {
  const spot = quietSide(y, text, dots, bounds);
  return (
    <g className="yardstick">
      <line x1={bounds.left} x2={bounds.right} y1={y} y2={y} />
      <text x={spot.x} y={spot.y} textAnchor={spot.anchor}>
        {text}
      </text>
    </g>
  );
}

export function ModelChart({
  entries,
  axis,
  chosen,
}: Readonly<{ entries: BenchmarkEntry[]; axis: Axis; chosen: string | null }>) {
  const [hover, setHover] = useState<Placed | null>(null);
  const models = entries.filter(
    (e) => e.kind === "model" && (across(e, axis) ?? 0) > 0,
  );
  const yardsticks = entries.filter((e) => e.kind === "yardstick");
  if (models.length === 0) return null;

  const xs = models.map((e) => across(e, axis) ?? 0);
  const log = axis === "cost";
  const [x0, x1] = log
    ? [Math.min(...xs) / 1.6, Math.max(...xs) * 1.6]
    : [0, Math.max(...xs) * 1.1];
  const ys = [
    ...models.flatMap((e) => [e.net_low, e.net_high]),
    ...yardsticks.map((e) => e.net_chf),
    0,
  ];
  const pad = (Math.max(...ys) - Math.min(...ys)) * 0.06 || 1;
  const [y0, y1] = [Math.min(...ys) - pad, Math.max(...ys) + pad];
  const left = PAD.left;
  const width = W - PAD.left - PAD.right;
  const sx = (v: number) =>
    log
      ? left + ((Math.log10(v) - Math.log10(x0)) / Math.log10(x1 / x0)) * width
      : left + ((v - x0) / (x1 - x0)) * width;
  const sy = (v: number) =>
    H - PAD.bottom - ((v - y0) / (y1 - y0)) * (H - PAD.top - PAD.bottom);
  const placed: Placed[] = models.map((e) => ({
    e,
    x: sx(across(e, axis) ?? 0),
    y: sy(e.net_chf),
  }));
  const onFront = (e: BenchmarkEntry) => (log ? e.front_cost : e.front_time);
  const front = placed.filter((p) => onFront(p.e)).sort((a, b) => a.x - b.x);
  const zero = sy(0);
  const bounds = {
    left,
    right: W - PAD.right,
    top: PAD.top,
    bottom: H - PAD.bottom,
  };
  const named = placed.filter((p) => onFront(p.e) || p.e.model === chosen);
  const name = (e: BenchmarkEntry) =>
    e.model === chosen ? `${e.label}, picked` : e.label;
  const spots = placeLabels(
    named.map((p) => ({ x: p.x, y: p.y, text: name(p.e) })),
    placed,
    bounds,
    [
      ...front.slice(1).map((p, i) => [front[i], p] as const),
      ...placed.map(
        (p) =>
          [
            { x: p.x, y: sy(p.e.net_low) },
            { x: p.x, y: sy(p.e.net_high) },
          ] as const,
      ),
    ],
  );
  const labelOf = new Map(named.map((p, i) => [p.e.model, spots[i]]));
  const xTicks = log ? logTicks(x0, x1) : linearTicks(x0, x1);

  return (
    <div className="chart">
      <ul className="legend" aria-label="Key">
        <li>
          <span className="key-dot key-front" /> On the front
        </li>
        <li>
          <span className="key-dot key-beaten" /> Beaten: another saves more for
          less
        </li>
        <li>
          <span className="key-line key-yardstick" /> Free yardstick
        </li>
      </ul>
      <svg
        viewBox={`0 0 ${W.toString()} ${H.toString()}`}
        role="img"
        aria-label={`${models.length.toString()} models, each plotted by net saving per ticket against ${log ? "model cost per 1'000 tickets" : "median time per ticket"}. The table below has the same numbers.`}
      >
        <rect
          className="pays"
          x={left}
          y={PAD.top}
          width={width}
          height={Math.max(zero - PAD.top, 0)}
        />
        {linearTicks(y0, y1).map((v) => (
          <g key={`y${v.toString()}`} className="grid">
            <line x1={left} x2={W - PAD.right} y1={sy(v)} y2={sy(v)} />
            <text x={left - 8} y={sy(v) + 4} textAnchor="end">
              {v.toLocaleString("de-CH")}
            </text>
          </g>
        ))}
        {xTicks.map((v) => (
          <text
            key={`x${v.toString()}`}
            className="tick"
            x={sx(v)}
            y={H - PAD.bottom + 18}
            textAnchor="middle"
          >
            {tickLabel(v, axis)}
          </text>
        ))}
        <line
          className="zero"
          x1={left}
          x2={W - PAD.right}
          y1={zero}
          y2={zero}
        />
        {yardsticks.map((e) => (
          <Yardstick
            key={e.model}
            text={`${e.label}, free: ${francs(e.net_chf)}`}
            y={sy(e.net_chf)}
            dots={placed}
            bounds={bounds}
          />
        ))}
        {front.length > 1 && (
          <polyline
            className="front-line"
            points={front
              .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
              .join(" ")}
          />
        )}
        {placed.map((p) => {
          const kind = onFront(p.e) ? "front" : "beaten";
          const picked = p.e.model === chosen;
          const spot = labelOf.get(p.e.model);
          return (
            <g
              key={p.e.model}
              className={`model model-${kind}${p.e.sample ? " model-sample" : ""}${picked ? " model-picked" : ""}`}
              onMouseEnter={() => {
                setHover(p);
              }}
              onMouseLeave={() => {
                setHover(null);
              }}
            >
              <line
                className="model-range"
                x1={p.x}
                x2={p.x}
                y1={sy(p.e.net_low)}
                y2={sy(p.e.net_high)}
              />
              <circle className="dot-hit" cx={p.x} cy={p.y} r={12} />
              <circle
                className="model-mark"
                cx={p.x}
                cy={p.y}
                r={picked ? 7 : 5}
              />
              {spot && (
                <text
                  className="model-label"
                  x={spot.x}
                  y={spot.y}
                  textAnchor={spot.anchor}
                >
                  {name(p.e)}
                </text>
              )}
            </g>
          );
        })}
        <text className="axis" x={W - PAD.right} y={H - 6} textAnchor="end">
          {log
            ? "Model cost per 1'000 tickets, CHF, on a log scale"
            : "Median time per ticket"}
        </text>
        <text className="axis" x={8} y={16}>
          Net saving per ticket, CHF
        </text>
      </svg>
      {hover && <ModelTip at={hover} />}
    </div>
  );
}
