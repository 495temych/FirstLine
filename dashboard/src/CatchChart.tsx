import { useState, type MouseEvent } from "react";
import type { BusinessCase, Layer } from "./api";
import { francs, percent } from "./format";

const W = 640;
const H = 320;
const PAD = { left: 64, right: 24, top: 28, bottom: 40 };

/** Net saving at a share caught, on the straight line between its two ends. */
const at = (layer: Layer, caught: number) =>
  layer.net_none_caught +
  (layer.net_all_caught - layer.net_none_caught) * caught;

function niceTicks(lo: number, hi: number) {
  const raw = (hi - lo) / 5;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
    out.push(Math.round(v * 1000) / 1000);
  }
  return out;
}

interface Series {
  name: string;
  layer: Layer;
  className: string;
  caught: number;
}

export function CatchChart({ data }: Readonly<{ data: BusinessCase }>) {
  const [hover, setHover] = useState<number | null>(null);
  const series: Series[] = [];
  if (data.projected) {
    series.push({
      name: "Projected",
      layer: data.projected,
      className: "line-projected",
      caught: data.rates.catch_rate,
    });
  }
  if (data.observed) {
    series.push({
      name: "Observed",
      layer: data.observed,
      className: "line-observed",
      caught: data.observed.catch_rate,
    });
  }
  if (series.length === 0) return null;

  const ends = series.flatMap((s) => [
    s.layer.net_none_caught,
    s.layer.net_all_caught,
  ]);
  const lo = Math.min(...ends, 0);
  const hi = Math.max(...ends, 0);
  const pad = (hi - lo) * 0.08 || 1;
  const yd = [lo - pad, hi + pad] as const;
  const sx = (v: number) => PAD.left + v * (W - PAD.left - PAD.right);
  const sy = (v: number) =>
    H -
    PAD.bottom -
    ((v - yd[0]) / (yd[1] - yd[0])) * (H - PAD.top - PAD.bottom);
  const zero = sy(0);

  const track = (event: MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * W;
    const caught = (x - PAD.left) / (W - PAD.left - PAD.right);
    setHover(caught >= 0 && caught <= 1 ? caught : null);
  };

  return (
    <div className="chart">
      <ul className="legend" aria-label="Key">
        {series.map((s) => (
          <li key={s.name}>
            <span className={`key-line ${s.className}`} /> {s.name}
          </li>
        ))}
      </ul>
      <svg
        viewBox={`0 0 ${W.toString()} ${H.toString()}`}
        role="img"
        aria-label="Net saving per ticket against the share of wrong decisions technicians catch. The table below has the same numbers."
        onMouseMove={track}
        onMouseLeave={() => {
          setHover(null);
        }}
      >
        <rect
          className="pays"
          x={PAD.left}
          y={PAD.top}
          width={W - PAD.left - PAD.right}
          height={Math.max(zero - PAD.top, 0)}
        />
        {niceTicks(yd[0], yd[1]).map((v) => (
          <g key={`y${v.toString()}`} className="grid">
            <line x1={PAD.left} x2={W - PAD.right} y1={sy(v)} y2={sy(v)} />
            <text x={PAD.left - 8} y={sy(v) + 4} textAnchor="end">
              {v.toLocaleString("de-CH")}
            </text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <text
            key={`x${v.toString()}`}
            className="tick"
            x={sx(v)}
            y={H - PAD.bottom + 18}
            textAnchor="middle"
          >
            {percent(v)}
          </text>
        ))}
        <line
          className="zero"
          x1={PAD.left}
          x2={W - PAD.right}
          y1={zero}
          y2={zero}
        />
        <text className="zero-label" x={PAD.left + 8} y={zero - 6}>
          Pays above this line
        </text>
        {series.map((s) => (
          <g key={s.name} className={s.className}>
            <line
              x1={sx(0)}
              y1={sy(s.layer.net_none_caught)}
              x2={sx(1)}
              y2={sy(s.layer.net_all_caught)}
            />
            <circle cx={sx(s.caught)} cy={sy(at(s.layer, s.caught))} r={5} />
            <text
              x={sx(s.caught) + (s.caught < 0.5 ? 10 : -10)}
              y={sy(at(s.layer, s.caught)) - 10}
              textAnchor={s.caught < 0.5 ? "start" : "end"}
            >
              {s.name}, {percent(s.caught)} caught
            </text>
          </g>
        ))}
        {hover !== null && (
          <line
            className="crosshair"
            x1={sx(hover)}
            x2={sx(hover)}
            y1={PAD.top}
            y2={H - PAD.bottom}
          />
        )}
        <text className="axis" x={W - PAD.right} y={H - 6} textAnchor="end">
          Share of wrong decisions technicians catch
        </text>
        <text className="axis" x={8} y={16}>
          Net saving per ticket, CHF
        </text>
      </svg>
      {hover !== null && (
        <div
          className="chart-tip"
          style={{
            left: `${((sx(hover) / W) * 100).toFixed(1)}%`,
            top: `${((PAD.top / H) * 100).toFixed(1)}%`,
          }}
          role="status"
        >
          <strong>{percent(hover)} caught</strong>
          {series.map((s) => (
            <span key={s.name}>
              {s.name}: {francs(at(s.layer, hover))}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
