import { useState, type CSSProperties } from "react";
import {
  api,
  type Evaluation,
  type Decisions,
  type Evaluations,
  type Summary,
} from "./api";
import { chf, dateTime, pathLabels, percent, rappen, rate } from "./format";
import { useLoad } from "./useLoad";

const setNames: Record<string, string> = {
  kb: "knowledge base",
  dev: "development",
  held_out: "held-out",
  rules: "rules set",
  rules_held_out: "rules set, held-out",
  unseen_dev: "unseen, development",
  unseen_held_out: "unseen, held-out",
};

function withMargin(share: number | null, margin: number | null) {
  if (share === null || margin === null) return "n/a";
  return `${percent(share)} ±${percent(margin)}`;
}

function setName(run: Evaluation) {
  const kinds = [
    run.tiny && "tiny",
    run.sample && "sample",
    run.rescored_from && "re-scored",
  ].filter(Boolean);
  const name = setNames[run.set];
  return kinds.length ? `${name} (${kinds.join(", ")})` : name;
}

function Runs({ runs }: Readonly<{ runs: Evaluation[] }>) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {[
              "Date",
              "Set",
              "Model",
              "Version",
              "Tickets",
              "Path",
              "Action",
              "Team",
              "Cause",
              "Retrieval",
              "Automation",
              "Mistakes (CHF)",
              "Cost per ticket",
              "Time per ticket",
            ].map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const s = run.summary;
            return (
              <tr key={run.id}>
                <td>{dateTime(run.date)}</td>
                <td>{setName(run)}</td>
                <td>
                  <code>{run.model}</code>
                </td>
                <td>
                  <code>{run.version}</code>
                </td>
                <td>{s.n}</td>
                <td>{withMargin(s.path_accuracy, s.path_margin)}</td>
                <td>{withMargin(s.action_accuracy, s.action_margin)}</td>
                <td>{withMargin(s.team_accuracy, s.team_margin)}</td>
                <td>{rate(s.cause_accuracy)}</td>
                <td>{percent(s.retrieval_accuracy)}</td>
                <td>{percent(s.automation_rate)}</td>
                <td>{chf(s.mistake_cost_chf)}</td>
                <td>{rappen(s.cost_per_ticket_chf)}</td>
                <td>{s.time_per_ticket_sec.toFixed(1)} s</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Head({ names }: Readonly<{ names: string[] }>) {
  return (
    <thead>
      <tr>
        {names.map((name) => (
          <th key={name} scope="col">
            {name}
          </th>
        ))}
      </tr>
    </thead>
  );
}

function Yardsticks({ run }: Readonly<{ run: Evaluation }>) {
  const rows: [string, Decisions][] = [
    ["FirstLine", run.summary],
    ["Simple classifier", run.yardsticks.classifier],
    ["Most common answer", run.yardsticks.most_common],
  ];
  return (
    <div className="table-scroll">
      <table>
        <Head
          names={["Who", "Path", "Action", "Team", "Kappa", "Mistakes (CHF)"]}
        />
        <tbody>
          {rows.map(([who, s]) => (
            <tr key={who}>
              <td>{who}</td>
              <td>{withMargin(s.path_accuracy, s.path_margin)}</td>
              <td>{withMargin(s.action_accuracy, s.action_margin)}</td>
              <td>{withMargin(s.team_accuracy, s.team_margin)}</td>
              <td>{s.kappa === null ? "n/a" : s.kappa.toFixed(2)}</td>
              <td>{chf(s.mistake_cost_chf)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MatrixCell({
  expected,
  chosen,
  count,
  total,
}: Readonly<{
  expected: string;
  chosen: string;
  count: number;
  total: number;
}>) {
  const share = total ? count / total : 0;
  const label = `Expected ${pathLabels[expected]}, chose ${pathLabels[chosen]}: ${count.toString()} of ${total.toString()}`;
  return (
    <td
      className={expected === chosen ? "cell hit" : "cell miss"}
      style={
        { "--share": `${Math.round(share * 85).toString()}%` } as CSSProperties
      }
      data-strong={share >= 0.5}
      aria-label={label}
      title={label}
    >
      {total ? count : "–"}
      {count > 0 && <small>{percent(share)}</small>}
    </td>
  );
}

function Confusion({ run }: Readonly<{ run: Evaluation }>) {
  const paths = Object.keys(run.confusion);
  return (
    <>
      <div className="table-scroll">
        <table className="matrix">
          <thead>
            <tr>
              <th rowSpan={2}>Expected</th>
              <th colSpan={paths.length} className="axis">
                Agent chose
              </th>
              <th rowSpan={2}>Tickets</th>
              <th rowSpan={2}>Recall</th>
            </tr>
            <tr>
              {paths.map((path) => (
                <th key={path}>{pathLabels[path]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paths.map((expected) => {
              const row = run.confusion[expected];
              const total = Object.values(row).reduce((a, b) => a + b, 0);
              return (
                <tr key={expected}>
                  <th scope="row">{pathLabels[expected]}</th>
                  {paths.map((chosen) => (
                    <MatrixCell
                      key={chosen}
                      expected={expected}
                      chosen={chosen}
                      count={row[chosen]}
                      total={total}
                    />
                  ))}
                  <td>{total}</td>
                  <td>{rate(run.per_path[expected].recall)}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Precision</th>
              {paths.map((path) => (
                <td key={path}>{rate(run.per_path[path].precision)}</td>
              ))}
              <td />
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="caption">
        Each row is the path the label expected, and each column the path the
        agent chose. Green cells on the diagonal are right and orange ones are
        mistakes. The darker the cell, the larger its share of the row. Recall
        is the share of a row the agent got right, and precision the share of a
        column that was right.
      </p>
    </>
  );
}

function ByGroup({
  label,
  groups,
}: Readonly<{ label: string; groups: Record<string, Summary> }>) {
  return (
    <div className="table-scroll">
      <table>
        <Head
          names={[
            label,
            "Tickets",
            "Path",
            "Action",
            "Team",
            "Cause",
            "Mistakes (CHF)",
            "Cost per ticket",
          ]}
        />
        <tbody>
          {Object.entries(groups).map(([group, s]) => (
            <tr key={group}>
              <td>{group}</td>
              <td>{s.n}</td>
              <td>{percent(s.path_accuracy)}</td>
              <td>{percent(s.action_accuracy)}</td>
              <td>{rate(s.team_accuracy)}</td>
              <td>{rate(s.cause_accuracy)}</td>
              <td>{chf(s.mistake_cost_chf)}</td>
              <td>{rappen(s.cost_per_ticket_chf)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunTickets({ run }: Readonly<{ run: Evaluation }>) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {[
              "Result",
              "Ticket",
              "Text",
              "Difficulty",
              "Expected",
              "Agent",
              "Expected tool or queue",
              "Agent's tool or queue",
              "Mistake (CHF)",
              "Error",
            ].map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {run.tickets.map((t) => (
            <tr key={t.id}>
              <td className={t.action_correct ? "right" : "wrong"}>
                {t.action_correct ? "Correct" : "Wrong"}
              </td>
              <td>{t.id}</td>
              <td className="wide">{t.text}</td>
              <td>{t.difficulty}</td>
              <td>{t.expected_paths.map((p) => pathLabels[p]).join(" or ")}</td>
              <td>{pathLabels[t.path]}</td>
              <td>
                <code>
                  {[...t.expected_tools, ...t.expected_queues].join(", ")}
                </code>
              </td>
              <td>
                <code>{t.queue ?? t.tool ?? ""}</code>
              </td>
              <td>{chf(t.mistake_cost_chf)}</td>
              <td>{t.error ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Board({ runs, costs }: Readonly<Pick<Evaluations, "runs" | "costs">>) {
  const [chosen, setChosen] = useState(runs[0].id);
  const run = runs.find((candidate) => candidate.id === chosen);
  return (
    <>
      <h2>Saved evaluations</h2>
      <Runs runs={runs} />
      <p className="caption">
        Mistake costs are assumptions: CHF {chf(costs.security)} for a routine
        fix on a possible compromise, CHF {costs.wrong} for a wrong fix,
        needless escalation or declined request, and CHF {costs.minor} for the
        wrong tool or queue.
      </p>
      <label htmlFor="evaluation">Open an evaluation</label>
      <select
        id="evaluation"
        value={chosen}
        onChange={(event) => {
          setChosen(event.target.value);
        }}
      >
        {runs.map((candidate) => (
          <option key={candidate.id}>{candidate.id}</option>
        ))}
      </select>
      {run && (
        <>
          <h2>Against the yardsticks</h2>
          <Yardsticks run={run} />
          <p className="caption">
            Both yardsticks are free and learn from the knowledge base split.
            Kappa is agreement beyond chance, so always giving one answer scores
            0. The ± is the 95% margin of error, and a smaller gap than that may
            be noise.
          </p>
          <h2>Paths</h2>
          <Confusion run={run} />
          <h2>By family</h2>
          <ByGroup label="Family" groups={run.by_family} />
          <h2>By difficulty</h2>
          <ByGroup label="Difficulty" groups={run.by_difficulty} />
          <h2>By ticket</h2>
          <RunTickets run={run} />
        </>
      )}
    </>
  );
}

export function Scoreboard() {
  const { data, error } = useLoad(api.evaluations);
  if (error) return <p className="notice alert">{error}</p>;
  if (!data) return null;
  if (data.runs.length === 0) {
    return (
      <p className="notice">
        No evaluations yet. Run <code>uv run -m evals --tiny</code> to create
        one.
      </p>
    );
  }
  return (
    <>
      <Board runs={data.runs} costs={data.costs} />
      <p className="caption">
        Retrieval has its own tab, with every saved score.
      </p>
    </>
  );
}
