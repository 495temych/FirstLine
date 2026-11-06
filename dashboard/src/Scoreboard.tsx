import { useState } from "react";
import { api, type Evaluation, type Evaluations, type Summary } from "./api";
import { chf, dateTime, money, pathLabels, percent } from "./format";
import { useLoad } from "./useLoad";

function setName(run: Evaluation) {
  const name = run.set === "held_out" ? "held-out" : "development";
  return run.tiny ? `${name} (tiny)` : name;
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
                <td>{percent(s.path_accuracy)}</td>
                <td>{percent(s.action_accuracy)}</td>
                <td>{percent(s.retrieval_accuracy)}</td>
                <td>{percent(s.automation_rate)}</td>
                <td>{chf(s.mistake_cost_chf)}</td>
                <td>{money(s.cost_per_ticket_usd)}</td>
                <td>{s.time_per_ticket_sec.toFixed(1)} s</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ByDifficulty({
  levels,
}: Readonly<{ levels: Record<string, Summary> }>) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {["Difficulty", "Tickets", "Path", "Action", "Mistakes (CHF)"].map(
              (name) => (
                <th key={name} scope="col">
                  {name}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {Object.entries(levels).map(([level, s]) => (
            <tr key={level}>
              <td>{level}</td>
              <td>{s.n}</td>
              <td>{percent(s.path_accuracy)}</td>
              <td>{percent(s.action_accuracy)}</td>
              <td>{chf(s.mistake_cost_chf)}</td>
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

function Board({ runs, costs }: Readonly<Evaluations>) {
  const [chosen, setChosen] = useState(runs[0]?.id);
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
          <h2>By difficulty</h2>
          <ByDifficulty levels={run.by_difficulty} />
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
  return <Board runs={data.runs} costs={data.costs} />;
}
