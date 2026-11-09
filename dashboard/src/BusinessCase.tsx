import { useEffect, useState } from "react";
import { api, type BusinessCase as Case, type Layer, type Rates } from "./api";
import { CatchChart } from "./CatchChart";
import { chf, francs, minutes, percent, rappen, seconds } from "./format";

const yearly = (amount: number) => `CHF ${chf(Math.round(Math.abs(amount)))}`;

function needed(layer: Layer) {
  if (layer.catch_needed === null) return "No mistakes to catch";
  if (layer.catch_needed > 1) return "Can't pay, even catching all";
  return percent(layer.catch_needed);
}

function Lede({ data }: Readonly<{ data: Case }>) {
  const { projected: p, observed: o } = data;
  if (!p) {
    return (
      <p className="notice">
        No development evaluation is saved yet, so there is nothing to project.
        Run <code>uv run -m evals --set dev --sample</code> to create one.
      </p>
    );
  }
  const gains = p.net_chf >= 0;
  const caught = o ? o.wrong - o.slipped : 0;
  return (
    <section className="how-goal" aria-labelledby="worth">
      <h2 id="worth">
        {gains ? "Each ticket saves " : "Each ticket loses "}
        {francs(Math.abs(p.net_chf))} net, about {yearly(p.per_year_chf)} a
        year.
      </h2>
      <p>
        That holds if technicians catch {percent(p.catch_rate)} of the agent's
        wrong decisions.{" "}
        {p.catch_needed !== null && p.catch_needed <= 1 && (
          <>It pays only above {percent(p.catch_needed)}. </>
        )}
        {o && o.wrong > 0 && (
          <>
            In the Queue so far they caught {caught} of {o.wrong}.
          </>
        )}
      </p>
    </section>
  );
}

type Row = [string, (layer: Layer) => string, (layer: Layer) => string];

const rows: Row[] = [
  [
    "Approved unchanged",
    (l) => `${percent(l.share)} ±${percent(l.share_margin)}`,
    (l) => `${percent(l.share)} ±${percent(l.share_margin)}`,
  ],
  [
    "Break-even share",
    (l) => percent(l.break_even),
    (l) => percent(l.break_even),
  ],
  [
    "Review time per ticket",
    (l) => `${minutes(l.review_minutes)}, assumed`,
    (l) => `${seconds(l.review_minutes * 60)}, measured`,
  ],
  [
    "Technician time saved",
    (l) => minutes(l.minutes_saved),
    (l) => minutes(l.minutes_saved),
  ],
  ["Worth", (l) => francs(l.time_chf), (l) => francs(l.time_chf)],
  ["Model cost", (l) => rappen(l.model_chf), (l) => rappen(l.model_chf)],
  [
    "Mistakes caught",
    (l) => `${percent(l.catch_rate)}, assumed`,
    (l) => `${percent(l.catch_rate)}, measured`,
  ],
  [
    "Mistakes that slip through",
    (l) => francs(l.mistakes_chf),
    (l) => francs(l.mistakes_chf),
  ],
  ["Net saving per ticket", (l) => francs(l.net_chf), (l) => francs(l.net_chf)],
  [
    "Its range, from the margin",
    (l) => `${francs(l.net_low)} to ${francs(l.net_high)}`,
    (l) => `${francs(l.net_low)} to ${francs(l.net_high)}`,
  ],
  ["Share caught it needs", needed, needed],
];

function Layers({ data }: Readonly<{ data: Case }>) {
  const { projected: p, observed: o } = data;
  return (
    <div className="table-scroll">
      <table className="layers">
        <thead>
          <tr>
            <th scope="col">Per ticket</th>
            <th scope="col">
              Projected
              <span className="quiet">
                {" "}
                {p ? `${p.n.toString()} labelled tickets` : "no evaluation"}
              </span>
            </th>
            <th scope="col">
              Observed
              <span className="quiet">
                {" "}
                {o ? `${o.n.toString()} Queue reviews` : "no reviews yet"}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, fromProjected, fromObserved]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td>{p ? fromProjected(p) : "n/a"}</td>
              <td>{o ? fromObserved(o) : "n/a"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Slider({
  id,
  label,
  value,
  shown,
  range,
  onChange,
}: Readonly<{
  id: string;
  label: string;
  value: number;
  shown: string;
  range: [number, number, number];
  onChange: (value: number) => void;
}>) {
  const [min, max, step] = range;
  return (
    <div className="slider">
      <label htmlFor={id}>
        {label} <output htmlFor={id}>{shown}</output>
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => {
          onChange(Number(event.target.value));
        }}
      />
    </div>
  );
}

function WhatIf({
  rates,
  onChange,
}: Readonly<{ rates: Rates; onChange: (rates: Rates) => void }>) {
  return (
    <fieldset className="what-if">
      <legend>What if an assumption is wrong?</legend>
      <Slider
        id="minutes-by-hand"
        label="A first pass by hand takes"
        value={rates.minutes_by_hand}
        shown={`${rates.minutes_by_hand.toString()} min`}
        range={[5, 30, 1]}
        onChange={(v) => {
          onChange({ ...rates, minutes_by_hand: v });
        }}
      />
      <Slider
        id="chf-per-hour"
        label="A technician costs"
        value={rates.chf_per_hour}
        shown={`CHF ${rates.chf_per_hour.toString()} an hour`}
        range={[40, 150, 5]}
        onChange={(v) => {
          onChange({ ...rates, chf_per_hour: v });
        }}
      />
      <Slider
        id="catch-rate"
        label="Technicians catch"
        value={rates.catch_rate}
        shown={`${percent(rates.catch_rate)} of mistakes`}
        range={[0.5, 1, 0.01]}
        onChange={(v) => {
          onChange({ ...rates, catch_rate: v });
        }}
      />
    </fieldset>
  );
}

/** The economics for the reader's assumptions, asked again as they move. */
function useCase() {
  const [rates, setRates] = useState<Rates>();
  const [data, setData] = useState<Case>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let current = true;
    const timer = setTimeout(() => {
      api
        .business(rates)
        .then((value) => {
          if (current) setData(value);
        })
        .catch((reason: unknown) => {
          if (current) setError(String(reason).replace(/^Error: /, ""));
        });
    }, 150);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [rates]);

  return { data, error, rates: rates ?? data?.rates, setRates };
}

export function BusinessCase() {
  const { data, error, rates, setRates } = useCase();
  if (error) {
    return (
      <p className="notice alert" role="alert">
        {error}
      </p>
    );
  }
  if (!data || !rates) return null;
  const a = data.assumptions;
  return (
    <div className="how business">
      <Lede data={data} />
      <section className="how-section" aria-labelledby="catching">
        <h2 id="catching">Where the case turns</h2>
        <p>
          Every decision is reviewed, so a wrong one costs money only when the
          technician misses it. The more they catch, the more each ticket saves.
        </p>
        <CatchChart data={data} />
        <WhatIf rates={rates} onChange={setRates} />
      </section>
      <section className="how-section" aria-labelledby="layers">
        <h2 id="layers">Projected and observed</h2>
        <Layers data={data} />
        <p className="caption">
          Projected counts a decision right in full as approved unchanged, on
          the development tickets
          {data.projected && (
            <>
              {" "}
              in run <code>{data.projected.source}</code>
            </>
          )}
          . Observed reads the Queue's reviews, and the labels say which
          approved decisions were wrong. A mistake costs CHF{" "}
          {chf(a.mistakes.security)} if it was a routine fix on a possible
          compromise, CHF {a.mistakes.wrong} for a wrong fix or needless
          escalation, and CHF {a.mistakes.minor} for the wrong tool or team. A
          year is {chf(a.tickets_per_year)} tickets. The assumptions are in
          BUSINESS_GOAL.md. These are practice tickets: the held-out sets run
          once, at the end.
        </p>
      </section>
    </div>
  );
}
