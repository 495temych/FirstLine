import { useState } from "react";
import {
  api,
  type Evaluation,
  type Decisions,
  type Evaluations,
  type RetrievalRun,
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
  const name = setNames[run.set];
  return run.tiny ? `${name} (tiny)` : name;
}

function RetrievalRuns({ runs }: Readonly<{ runs: RetrievalRun[] }>) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {[
              "Date",
              "Set",
              "Knowledge base",
              "Tickets",
              "Hit rate",
              "Reciprocal rank",
              "Recall",
              "False matches",
            ].map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>{dateTime(run.date)}</td>
              <td>{setNames[run.set]}</td>
              <td>
                <code>{run.kb_version}</code>
              </td>
              <td>{run.summary.n}</td>
              <td>{rate(run.summary.hit_rate)}</td>
              <td>{rate(run.summary.mean_reciprocal_rank)}</td>
              <td>{rate(run.summary.recall)}</td>
              <td>{rate(run.summary.false_match_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RetrievalFamilies({ run }: Readonly<{ run: RetrievalRun }>) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {["Family", "Playbook", "Tickets", "Hit rate", "False matches"].map(
              (name) => (
                <th key={name} scope="col">
                  {name}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {Object.entries(run.by_family).map(([code, family]) => (
            <tr key={code}>
              <td>{family.name}</td>
              <td>
                <code>{family.doc ?? "None"}</code>
              </td>
              <td>{family.n}</td>
              <td>{rate(family.hit_rate)}</td>
              <td>{rate(family.false_match_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Retrieval({ runs }: Readonly<{ runs: RetrievalRun[] }>) {
  const [chosen, setChosen] = useState(runs[0].id);
  const run = runs.find((candidate) => candidate.id === chosen) ?? runs[0];
  return (
    <>
      <h2>Retrieval</h2>
      <RetrievalRuns runs={runs} />
      <p className="caption">
        The hit rate is the share of tickets whose top match is their family's
        playbook. False matches are tickets from a family with no playbook that
        still matched a playbook. Reciprocal rank shows how high the right
        playbook ranks, and recall how often it's in the first two. These scores
        need no model calls.
      </p>
      <label htmlFor="retrieval">Open a retrieval score</label>
      <select
        id="retrieval"
        value={chosen}
        onChange={(event) => {
          setChosen(event.target.value);
        }}
      >
        {runs.map((candidate) => (
          <option key={candidate.id}>{candidate.id}</option>
        ))}
      </select>
      <RetrievalFamilies run={run} />
    </>
  );
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

function Confusion({ run }: Readonly<{ run: Evaluation }>) {
  const paths = Object.keys(run.confusion);
  return (
    <div className="table-scroll">
      <table>
        <Head
          names={[
            "Expected",
            ...paths.map((path) => `Chose ${pathLabels[path]}`),
            "Tickets",
            "Precision",
            "Recall",
          ]}
        />
        <tbody>
          {paths.map((expected) => (
            <tr key={expected}>
              <td>{pathLabels[expected]}</td>
              {paths.map((chosen) => (
                <td key={chosen}>{run.confusion[expected][chosen]}</td>
              ))}
              <td>{run.per_path[expected].n}</td>
              <td>{rate(run.per_path[expected].precision)}</td>
              <td>{rate(run.per_path[expected].recall)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
  if (data.runs.length === 0 && data.retrieval.length === 0) {
    return (
      <p className="notice">
        No evaluations yet. Run <code>uv run -m evals --tiny</code> to create
        one.
      </p>
    );
  }
  return (
    <>
      {data.runs.length > 0 && <Board runs={data.runs} costs={data.costs} />}
      {data.retrieval.length > 0 && <Retrieval runs={data.retrieval} />}
    </>
  );
}
