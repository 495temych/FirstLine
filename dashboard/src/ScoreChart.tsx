import { useState, type CSSProperties } from "react";
import type { RankedPlaybook, RetrievalView } from "./api";
import type { Point } from "./points";

type Rule = RetrievalView["rule"];

const W = 640;
const H = 400;
const PAD = { left: 52, right: 16, top: 36, bottom: 44 };

function domain(values: number[], extra: number[]) {
  const all = [...values, ...extra];
  const lo = Math.floor((Math.min(...all) - 0.02) * 20) / 20;
  const hi = Math.ceil((Math.max(...all) + 0.02) * 20) / 20;
  return [lo, hi] as const;
}

function ticks([lo, hi]: readonly [number, number]) {
  const out = [];
  for (let v = Math.ceil(lo * 10) / 10; v <= hi + 1e-9; v += 0.1) {
    out.push(Math.round(v * 10) / 10);
  }
  return out;
}

const two = (n: number) => n.toFixed(2);

function Dot({
  point,
  at,
  chosen,
  onHover,
  onSelect,
}: Readonly<{
  point: Point;
  at: { x: number; y: number };
  chosen: boolean;
  onHover: (point: Point | null) => void;
  onSelect: (id: string) => void;
}>) {
  const kind = point.covered ? "covered" : "uncovered";
  return (
    <g
      className={`dot dot-${kind}${point.wrong ? " dot-wrong" : ""}${chosen ? " dot-chosen" : ""}`}
      onMouseEnter={() => {
        onHover(point);
      }}
      onMouseLeave={() => {
        onHover(null);
      }}
      onClick={() => {
        onSelect(point.ticket.id);
      }}
    >
      <circle className="dot-hit" cx={at.x} cy={at.y} r={10} />
      <circle className="dot-mark" cx={at.x} cy={at.y} r={4.5} />
      {point.wrong && (
        <text className="dot-label" x={at.x + 8} y={at.y - 8}>
          {point.ticket.id}
        </text>
      )}
    </g>
  );
}

/** Where a match is accepted: high enough alone, or above the threshold and well
 * ahead of the next playbook. */
function acceptedArea(
  rule: Rule,
  sx: (v: number) => number,
  sy: (v: number) => number,
  [x0, x1]: readonly [number, number],
  [y0, y1]: readonly [number, number],
) {
  const corners: [number, number][] = [
    [rule.threshold, y0],
    [rule.threshold, rule.threshold - rule.margin],
    [rule.sure, rule.sure - rule.margin],
    [rule.sure, y1],
    [x1, y1],
    [x1, y0],
  ];
  return corners
    .map(([x, y]) => `${two(sx(Math.max(x, x0)))},${two(sy(Math.max(y, y0)))}`)
    .join(" ");
}

export function ScoreChart({
  all,
  rule,
  chosen,
  onSelect,
}: Readonly<{
  all: Point[];
  rule: Rule;
  chosen: string | null;
  onSelect: (id: string) => void;
}>) {
  const [hover, setHover] = useState<Point | null>(null);
  const xd = domain(
    all.map((p) => p.x),
    [rule.threshold, rule.sure],
  );
  const yd = domain(
    all.map((p) => p.y),
    [rule.threshold - rule.margin],
  );
  const sx = (v: number) =>
    PAD.left + ((v - xd[0]) / (xd[1] - xd[0])) * (W - PAD.left - PAD.right);
  const sy = (v: number) =>
    H -
    PAD.bottom -
    ((v - yd[0]) / (yd[1] - yd[0])) * (H - PAD.top - PAD.bottom);
  const diagonalTop = Math.min(xd[1], yd[1]);

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${W.toString()} ${H.toString()}`}
        role="img"
        aria-label={`${all.length.toString()} tickets, each plotted by the score of the playbook that should match against the best other one. The table below lists them.`}
      >
        <polygon
          className="accepted"
          points={acceptedArea(rule, sx, sy, xd, yd)}
        />
        {ticks(xd).map((v) => (
          <g key={`x${v.toString()}`} className="grid">
            <line x1={sx(v)} x2={sx(v)} y1={PAD.top} y2={H - PAD.bottom} />
            <text x={sx(v)} y={H - PAD.bottom + 18} textAnchor="middle">
              {v.toFixed(1)}
            </text>
          </g>
        ))}
        {ticks(yd).map((v) => (
          <g key={`y${v.toString()}`} className="grid">
            <line x1={PAD.left} x2={W - PAD.right} y1={sy(v)} y2={sy(v)} />
            <text x={PAD.left - 8} y={sy(v) + 4} textAnchor="end">
              {v.toFixed(1)}
            </text>
          </g>
        ))}
        <line
          className="even"
          x1={sx(Math.max(xd[0], yd[0]))}
          y1={sy(Math.max(xd[0], yd[0]))}
          x2={sx(diagonalTop)}
          y2={sy(diagonalTop)}
        />
        <g className="bar-line">
          <line
            x1={sx(rule.sure)}
            x2={sx(rule.sure)}
            y1={PAD.top}
            y2={H - PAD.bottom}
          />
          <text x={sx(rule.sure) + 6} y={PAD.top + 12}>
            Sure above {two(rule.sure)}
          </text>
          <line
            x1={sx(rule.threshold)}
            x2={sx(rule.sure)}
            y1={sy(rule.threshold - rule.margin)}
            y2={sy(rule.sure - rule.margin)}
          />
          <text
            x={sx(rule.sure) - 6}
            y={sy(rule.threshold - rule.margin) + 18}
            textAnchor="end"
          >
            {two(rule.margin)} ahead, from {two(rule.threshold)}
          </text>
        </g>
        {all.map((point) => (
          <Dot
            key={point.ticket.id}
            point={point}
            at={{ x: sx(point.x), y: sy(point.y) }}
            chosen={point.ticket.id === chosen}
            onHover={setHover}
            onSelect={onSelect}
          />
        ))}
        <text className="axis" x={W - PAD.right} y={H - 6} textAnchor="end">
          Score of the playbook that should match, or the best one
        </text>
        <text className="axis" x={8} y={16}>
          Best other playbook
        </text>
      </svg>
      {hover && (
        <div
          className="chart-tip"
          style={{
            left: `${((sx(hover.x) / W) * 100).toFixed(1)}%`,
            top: `${((sy(hover.y) / H) * 100).toFixed(1)}%`,
          }}
          role="status"
        >
          <strong>{hover.ticket.title}</strong>
          <span>
            {two(hover.x)} against {two(hover.y)}
          </span>
        </div>
      )}
    </div>
  );
}

/** Playbooks as bars on one scale, with the threshold and the sure line marked. */
export function ScoreBars({
  ranked,
  rule,
  expected,
}: Readonly<{
  ranked: RankedPlaybook[];
  rule: Rule;
  expected?: string | null;
}>) {
  const at = (v: number) => `${(v * 100).toFixed(1)}%`;
  return (
    <>
      <ol
        className="bars"
        style={
          {
            "--threshold": at(rule.threshold),
            "--sure": at(rule.sure),
          } as CSSProperties
        }
      >
        {ranked.map((r) => (
          <li key={r.doc} className={r.doc === expected ? "right" : undefined}>
            <span className="bar-name">
              <code>{r.doc}</code>
              {r.doc === expected && (
                <span className="quiet"> (should match)</span>
              )}
              {r.section && <span className="quiet"> {r.section}</span>}
            </span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: at(r.score) }} />
            </span>
            <span className="bar-value">{two(r.score)}</span>
          </li>
        ))}
      </ol>
      <p className="caption">
        The faint mark on each bar is the {two(rule.threshold)} threshold, the
        strong one the {two(rule.sure)} sure line.
      </p>
    </>
  );
}
