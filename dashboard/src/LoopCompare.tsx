import { useState } from "react";
import {
  linearTicks,
  perThousand,
  placeLabels,
  type BenchmarkSet,
  type LoopPair,
  type LoopVerdict,
  type LoopView,
} from "./benchmark";
import { francs, percent } from "./format";
import { Pills } from "./Pills";

const W = 640;
const H = 320;
const PAD = { left: 60, right: 24, top: 24, bottom: 44 };
const PER = 1000;

const setLabels: Record<BenchmarkSet, string> = {
  dev: "Development sample",
  unseen_dev: "Families with no playbook",
  rules: "Rules set",
};

const x = (cost: number | null) => (cost ?? 0) * PER;

/** Where an arrow from `a` should end so its head stops short of the dot at `b`. */
function short(a: { x: number; y: number }, b: { x: number; y: number }) {
  const length = Math.hypot(b.x - a.x, b.y - a.y);
  if (length < 1) return b;
  const keep = Math.max(length - 8, 0) / length;
  return { x: a.x + (b.x - a.x) * keep, y: a.y + (b.y - a.y) * keep };
}

/** Each model's one call and its loop, as an arrow from one to the other: net
 * saving per ticket against cost per 1'000 tickets. */
function ArrowChart({ pairs }: Readonly<{ pairs: LoopPair[] }>) {
  const xs = pairs.flatMap((p) => [x(p.one_call.cost_chf), x(p.loop.cost_chf)]);
  const ys = pairs.flatMap((p) => [p.one_call.net_chf, p.loop.net_chf]);
  const x1 = Math.max(...xs) * 1.15 || 1;
  const pad = (Math.max(...ys) - Math.min(...ys)) * 0.2 || 1;
  const y0 = Math.min(...ys, 0) - pad;
  const y1 = Math.max(...ys, 0) + pad;
  const left = PAD.left;
  const sx = (v: number) => left + (v / x1) * (W - PAD.right - left);
  const sy = (v: number) =>
    PAD.top + ((y1 - v) / (y1 - y0)) * (H - PAD.bottom - PAD.top);
  const placed = pairs.map((p) => ({
    p,
    from: { x: sx(x(p.one_call.cost_chf)), y: sy(p.one_call.net_chf) },
    to: { x: sx(x(p.loop.cost_chf)), y: sy(p.loop.net_chf) },
  }));
  const spots = placeLabels(
    placed.map((d) => ({ ...d.to, text: d.p.label })),
    placed.flatMap((d) => [d.from, d.to]),
    { left, right: W - PAD.right, top: PAD.top, bottom: H - PAD.bottom },
    placed.map((d) => [d.from, d.to] as const),
  );
  return (
    <div className="chart">
      <ul className="legend" aria-label="Key">
        <li>
          <span className="key-dot key-beaten" /> One call, on the same tickets
        </li>
        <li>
          <span className="key-dot key-front" /> The loop
        </li>
      </ul>
      <svg
        viewBox={`0 0 ${W.toString()} ${H.toString()}`}
        role="img"
        aria-label={`For ${pairs.length.toString()} models, an arrow from one call to the loop, by net saving per ticket against cost per 1'000 tickets. The table below has the same numbers.`}
      >
        <defs>
          <marker
            id="loop-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L10 5 L0 10 z" className="loop-arrowhead" />
          </marker>
        </defs>
        {linearTicks(y0, y1).map((v) => (
          <g key={`y${v.toString()}`} className="grid">
            <line x1={left} x2={W - PAD.right} y1={sy(v)} y2={sy(v)} />
            <text x={left - 8} y={sy(v) + 4} textAnchor="end">
              {v.toLocaleString("de-CH")}
            </text>
          </g>
        ))}
        {linearTicks(0, x1).map((v) => (
          <text
            key={`x${v.toString()}`}
            className="tick"
            x={sx(v)}
            y={H - PAD.bottom + 18}
            textAnchor="middle"
          >
            {v.toLocaleString("de-CH", { maximumFractionDigits: 2 })}
          </text>
        ))}
        <line
          className="zero"
          x1={left}
          x2={W - PAD.right}
          y1={sy(0)}
          y2={sy(0)}
        />
        {placed.map((d, i) => (
          <g key={d.p.model} className="loop-pair">
            <line
              className="loop-move"
              x1={d.from.x}
              y1={d.from.y}
              x2={short(d.from, d.to).x}
              y2={short(d.from, d.to).y}
              markerEnd="url(#loop-arrow)"
            />
            <circle className="loop-from" cx={d.from.x} cy={d.from.y} r={5} />
            <circle className="loop-to" cx={d.to.x} cy={d.to.y} r={5} />
            <text
              className="model-label"
              x={spots[i].x}
              y={spots[i].y}
              textAnchor={spots[i].anchor}
            >
              {d.p.label}
            </text>
          </g>
        ))}
        <text className="axis" x={W - PAD.right} y={H - 6} textAnchor="end">
          Model cost per 1&apos;000 tickets, CHF
        </text>
        <text className="axis" x={8} y={16}>
          Net saving per ticket, CHF
        </text>
      </svg>
    </div>
  );
}

const share = (v: number | null | undefined) =>
  v === null || v === undefined ? "n/a" : percent(v);

const step = (a: string, b: string) => `${a} → ${b}`;

function PairTable({ pairs }: Readonly<{ pairs: LoopPair[] }>) {
  return (
    <div className="table-scroll">
      <table className="models-table">
        <thead>
          <tr>
            {[
              "Model",
              "Net saving per ticket",
              "Cost per 1'000 tickets",
              "Right in full",
              "Security mistakes",
              "Lookups per ticket",
              "Labelled checks run",
              "Needless checks per ticket",
              "Citations of steps that ran",
            ].map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pairs.map(
            ({ model, label, n, same_instructions, one_call: one, loop }) => {
              const inv = loop.investigation;
              return (
                <tr key={model}>
                  <th scope="row">
                    {label}
                    <span className="quiet"> {n} tickets</span>
                    {!same_instructions && (
                      <span className="quiet">
                        , one call on older instructions
                      </span>
                    )}
                    <br />
                    <code className="quiet">{loop.source}</code>
                  </th>
                  <td>
                    {step(francs(one.net_chf), francs(loop.net_chf))}
                    <span className="quiet">
                      {" "}
                      loop {francs(loop.net_low)} to {francs(loop.net_high)}
                    </span>
                  </td>
                  <td>
                    {step(
                      perThousand(one.cost_chf),
                      perThousand(loop.cost_chf),
                    )}
                  </td>
                  <td>
                    {step(
                      percent(one.action_accuracy),
                      percent(loop.action_accuracy),
                    )}
                  </td>
                  <td>
                    {step(
                      String(one.security_mistakes ?? "n/a"),
                      String(loop.security_mistakes ?? "n/a"),
                    )}
                  </td>
                  <td>{inv?.lookups_per_ticket?.toFixed(1) ?? "n/a"}</td>
                  <td>
                    {inv && inv.required_checks > 0
                      ? `${inv.required_run.toString()} of ${inv.required_checks.toString()}`
                      : "none labelled"}
                  </td>
                  <td>{inv?.needless_per_ticket?.toFixed(1) ?? "n/a"}</td>
                  <td>
                    {inv && inv.citations > 0
                      ? `${share(inv.citations_valid)} of ${inv.citations.toString()}`
                      : "none cited"}
                  </td>
                </tr>
              );
            },
          )}
        </tbody>
      </table>
    </div>
  );
}

const yes = (ok: boolean) => (ok ? "yes" : "no");

function Verdicts({
  view,
  labels,
}: Readonly<{ view: LoopView; labels: Record<string, string> }>) {
  const entries = Object.entries(view.verdicts);
  if (entries.length === 0) return null;
  return (
    <dl className="insights">
      {entries.map(([model, v]: [string, LoopVerdict]) => (
        <div key={model}>
          <dt>
            {labels[model] ?? model}:{" "}
            {v.keep ? "keep the loop" : "stay on one call"}
          </dt>
          <dd>
            Saves {francs(Math.abs(v.gain_chf))}{" "}
            {v.gain_chf >= 0 ? "more" : "less"} a ticket for{" "}
            {perThousand(v.extra_cost_chf)} more per 1&apos;000 tickets in model
            cost. Clears the margin: {yes(v.saves_more)}. No security mistake on
            any set: {yes(v.safe)}. No more invalid answers than one call:{" "}
            {yes(v.valid)}. Under CHF 0.10 a ticket: {yes(v.cheap)}.
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Does investigating pay? Each model's loop beside its own one call, on the same
 * tickets, with the rule written before the runs. */
export function LoopCompare({ view }: Readonly<{ view: LoopView }>) {
  const [set, setSet] = useState<BenchmarkSet>("dev");
  const pairs = view.sets[set];
  const labels = Object.fromEntries(
    Object.values(view.sets)
      .flat()
      .map((p) => [p.model, p.label]),
  );
  const any = Object.values(view.sets).some((found) => found.length > 0);
  return (
    <section className="how-section" aria-labelledby="loop">
      <h2 id="loop">Does investigating pay?</h2>
      <p>
        The loop lets a model look things up before it decides. Each arrow runs
        from a model&apos;s one call to its loop, on the same tickets, so the
        only difference is the investigating.
      </p>
      {any ? (
        <>
          <Verdicts view={view} labels={labels} />
          <Pills
            legend="Tickets"
            options={["dev", "unseen_dev", "rules"] as const}
            value={set}
            label={(s) => setLabels[s]}
            onChange={setSet}
          />
          {pairs.length === 0 ? (
            <p className="notice">No model has a loop run on this set yet.</p>
          ) : (
            <>
              <ArrowChart pairs={pairs} />
              <PairTable pairs={pairs} />
            </>
          )}
        </>
      ) : (
        <p className="notice">
          No model has a loop run yet. Run{" "}
          <code>uv run -m evals --set dev --sample --design loop</code> to make
          one.
        </p>
      )}
      <p className="caption">
        The rule, set before the runs:{" "}
        {view.rule.charAt(0).toLowerCase() + view.rule.slice(1)} One call&apos;s
        numbers come from its saved run, cut to the loop&apos;s tickets, with no
        new model calls. The samples are small, so only a large difference can
        show.
      </p>
    </section>
  );
}
