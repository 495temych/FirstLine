import { useState } from "react";
import { api } from "./api";
import { chf, francs, percent, seconds } from "./format";
import {
  perThousand,
  type Axis,
  type Benchmark,
  type BenchmarkEntry,
  type BenchmarkSet,
} from "./benchmark";
import { ModelChart } from "./ModelChart";
import { useLoad } from "./useLoad";

const setLabels: Record<BenchmarkSet, string> = {
  dev: "Development",
  unseen_dev: "Families with no playbook",
  rules: "Rules set",
};

const setQuestions: Record<BenchmarkSet, string> = {
  dev: "On the real mix of requests, what does each model save?",
  unseen_dev:
    "On families the knowledge base doesn't cover, does each model escalate as it should?",
  rules:
    "On short requests and policy traps, does each model keep to the rules?",
};

function Pills<T extends string>(
  props: Readonly<{
    legend: string;
    options: readonly T[];
    value: T;
    label: (option: T) => string;
    onChange: (value: T) => void;
  }>,
) {
  return (
    <fieldset className="pills">
      <legend>{props.legend}</legend>
      {props.options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={props.value === option}
          onClick={() => {
            props.onChange(option);
          }}
        >
          {props.label(option)}
        </button>
      ))}
    </fieldset>
  );
}

function Lede({ data }: Readonly<{ data: Benchmark }>) {
  const dev = data.sets.dev.entries;
  const pick = dev.find((e) => e.model === data.chosen?.model);
  const best = dev.find((e) => e.model === data.chosen?.best);
  if (!data.chosen) {
    return (
      <p className="notice">
        No model has a development run yet. Run{" "}
        <code>uv run -m evals --set dev --model gpt-6-luna</code> to make one.
      </p>
    );
  }
  return (
    <section className="how-goal" aria-labelledby="pick">
      <h2 id="pick">
        {pick
          ? `Run FirstLine on ${pick.label}. It saves ${francs(pick.net_chf)} a ticket, for ${perThousand(pick.cost_chf)} per 1'000 tickets.`
          : "No model passes the rule yet."}
      </h2>
      <p>
        The rule, set before the runs: {data.rule.toLowerCase()}
        {pick && best && best.model !== pick.model && (
          <>
            {" "}
            {best.label} saves {francs(best.net_chf - pick.net_chf)} more a
            ticket, within the margin, for {perThousand(best.cost_chf)} per
            1&apos;000.
          </>
        )}
      </p>
    </section>
  );
}

function Insights({ data }: Readonly<{ data: Benchmark }>) {
  if (data.insights.length === 0) return null;
  return (
    <section className="how-section" aria-labelledby="show">
      <h2 id="show">What the runs show</h2>
      <dl className="insights">
        {data.insights.map((i) => (
          <div key={i.question}>
            <dt>{i.question}</dt>
            <dd>{i.answer}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function served(e: BenchmarkEntry) {
  if (!e.serving) return "free, on this machine";
  const s = e.serving;
  const where = s.region === "unconfirmed" ? "region unconfirmed" : s.region;
  const effort = s.effort ? `, effort ${s.effort}` : "";
  return `${s.provider ?? s.lab}, ${where}${effort}`;
}

function Table({
  entries,
  chosen,
}: Readonly<{ entries: BenchmarkEntry[]; chosen: string | null }>) {
  return (
    <div className="table-scroll">
      <table className="models-table">
        <thead>
          <tr>
            {[
              "Model",
              "Served by",
              "Net saving per ticket",
              "Cost per 1'000 tickets",
              "Median, 90th percentile time",
              "Right in full",
              "Path, balanced",
              "Mistakes (CHF)",
              "Security mistakes",
              "Invalid",
              "Front",
            ].map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr
              key={e.model}
              className={e.kind === "yardstick" ? "quiet-row" : undefined}
            >
              <th scope="row">
                {e.label}
                {e.model === chosen && <span className="quiet"> picked</span>}
                {e.sample && <span className="quiet"> sample</span>}
                <br />
                <code className="quiet">{e.source}</code>
              </th>
              <td>{served(e)}</td>
              <td>
                {francs(e.net_chf)}
                <span className="quiet">
                  {" "}
                  {francs(e.net_low)} to {francs(e.net_high)}
                </span>
              </td>
              <td>
                {e.kind === "yardstick" ? "free" : perThousand(e.cost_chf)}
              </td>
              <td>
                {e.kind === "yardstick"
                  ? "n/a"
                  : `${seconds(e.time_p50_sec)}, ${seconds(e.time_p90_sec)}`}
              </td>
              <td>
                {percent(e.action_accuracy)} of {e.n}
              </td>
              <td>
                {percent(e.path_accuracy)} ±{percent(e.path_margin)}
                {e.balanced_accuracy !== null && (
                  <span className="quiet">
                    {" "}
                    {percent(e.balanced_accuracy)} balanced
                  </span>
                )}
              </td>
              <td>{chf(e.mistake_cost_chf)}</td>
              <td>{e.security_mistakes ?? "n/a"}</td>
              <td>{e.invalid}</td>
              <td>
                {e.kind === "yardstick"
                  ? "the bar"
                  : [e.front_cost && "cost", e.front_time && "time"]
                      .filter(Boolean)
                      .join(", ") || "beaten"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Models() {
  const { data, error } = useLoad(api.benchmark);
  const [set, setSet] = useState<BenchmarkSet>("dev");
  const [axis, setAxis] = useState<Axis>("cost");
  if (error) {
    return (
      <p className="notice alert" role="alert">
        {error}
      </p>
    );
  }
  if (!data) return null;
  const entries = data.sets[set].entries;
  const chosen = data.chosen?.model ?? null;
  const n = entries.find((e) => e.kind === "model")?.n;
  return (
    <div className="how models">
      <Lede data={data} />
      <Insights data={data} />
      <section className="how-section" aria-labelledby="where">
        <h2 id="where">Where each model sits</h2>
        <p>{setQuestions[set]}</p>
        <div className="filters">
          <Pills
            legend="Tickets"
            options={["dev", "unseen_dev", "rules"] as const}
            value={set}
            label={(s) => setLabels[s]}
            onChange={setSet}
          />
          <Pills
            legend="Across"
            options={["cost", "time"] as const}
            value={axis}
            label={(a) => (a === "cost" ? "Cost" : "Time")}
            onChange={setAxis}
          />
        </div>
        {entries.length === 0 ? (
          <p className="notice">
            No model has a run on this set yet. Run{" "}
            <code>uv run -m evals --set {set} --model gpt-6-luna</code>.
          </p>
        ) : (
          <>
            <ModelChart entries={entries} axis={axis} chosen={chosen} />
            <p className="caption">
              Each dot is one model on {n ?? 0} tickets, and its line is the
              range its 95% margin allows. A model is on the front when no other
              saves at least as much for less. Net saving counts technician time
              saved, the model&apos;s cost, and the mistakes technicians miss,
              at {percent(data.catch_rate)} caught, as on the Money tab.
            </p>
            <Table entries={entries} chosen={chosen} />
          </>
        )}
        <p className="caption">
          Limits: each model ran once, so a gap inside the margin is a tie. The
          instructions were written for Claude, which may favour it. Qwen&apos;s
          only provider can&apos;t force the decision form, so it&apos;s only
          offered it, and an answer without it counts as invalid. A model with
          only a sample run is marked as one. These are practice tickets: the
          held-out sets run once, at the end.
        </p>
      </section>
    </div>
  );
}
