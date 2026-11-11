import { useState } from "react";
import {
  api,
  type Example,
  type Line,
  type Overview,
  type RoutePath,
  type StationInfo,
} from "./api";
import { pathLabels, percent, rappen, seconds } from "./format";
import { useLoad } from "./useLoad";

const ARRIVE = "arrive";
const ARRIVAL: StationInfo = {
  name: "A ticket arrives",
  does: "A request comes in from the service desk or the Assistant: a title, a description and who sent it.",
  cannot: "Nothing has been decided yet.",
  code: "start_triage in backend/main.py, load_batch in backend/queue_board.py",
  gate: false,
};

interface Selected {
  node: string;
  path: RoutePath;
}

function Stop(
  props: Readonly<{
    node: string;
    info: StationInfo;
    path: RoutePath;
    selected: Selected;
    onSelect: (selected: Selected) => void;
  }>,
) {
  const pressed =
    props.selected.node === props.node && props.selected.path === props.path;
  return (
    <li className={props.info.gate ? "map-stop gate" : "map-stop"}>
      <button
        type="button"
        aria-pressed={pressed}
        onClick={() => {
          props.onSelect({ node: props.node, path: props.path });
        }}
      >
        <span className="map-dot" aria-hidden="true" />
        <span>{props.info.name}</span>
        {props.info.gate && (
          <span className="sr-only"> (a person decides)</span>
        )}
      </button>
    </li>
  );
}

function RouteMap(
  props: Readonly<{
    overview: Overview;
    selected: Selected;
    onSelect: (selected: Selected) => void;
  }>,
) {
  const { overview, selected } = props;
  const stop = (node: string, path: RoutePath, info?: StationInfo) => (
    <Stop
      key={`${path}-${node}`}
      node={node}
      info={info ?? overview.stations[node]}
      path={path}
      selected={selected}
      onSelect={props.onSelect}
    />
  );
  const trunkPath = selected.path;
  return (
    <div className="map" aria-label="The route a ticket takes">
      <ol className="map-trunk">
        {stop(ARRIVE, trunkPath, ARRIVAL)}
        {overview.trunk.map((node) => stop(node, trunkPath))}
      </ol>
      <ul className="map-lines">
        {overview.lines.map((line: Line) => (
          <li
            key={line.path}
            className={`map-line path-${line.path}`}
            data-active={line.path === selected.path}
          >
            <h3 className="map-line-name">{line.label}</h3>
            <p className="map-means">{line.means}</p>
            <ol className="map-stops">
              {line.stations.map((node) => stop(node, line.path))}
              <li className="map-end">Done</li>
            </ol>
            {line.otherwise.length > 0 && (
              <>
                <p className="map-otherwise-when">{line.otherwise_when}</p>
                <ol className="map-stops otherwise">
                  {line.otherwise.map((node) => stop(node, line.path))}
                  <li className="map-end">Done</li>
                </ol>
              </>
            )}
            {line.otherwise.length === 0 && line.otherwise_when && (
              <p className="map-otherwise-when">{line.otherwise_when}.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** What the example ticket shows at this station, if anything. */
function seenHere(node: string, example: Example, path: RoutePath) {
  switch (node) {
    case ARRIVE:
      return `"${example.title}", a ${example.family.toLowerCase()} ticket.`;
    case "retrieve":
      return example.retrieved.length
        ? `It matched ${example.retrieved.join(" and ")}.`
        : "Nothing matched well enough, so no playbook was used.";
    case "triage":
      return `It found the likely cause, ${example.cause.toLowerCase()}, and chose ${pathLabels[path].toLowerCase()}.`;
    case "confirm_fix":
    case "execute_tool":
      return example.tool ? `The fix is ${example.tool}.` : null;
    case "confirm_ticket":
    case "create_ticket":
      return example.queue ? `The ticket goes to ${example.queue}.` : null;
    case "self_serve_wait":
      return example.retrieved.length
        ? `The steps come from ${example.retrieved[0]}.`
        : null;
    default:
      return null;
  }
}

function StationPanel(
  props: Readonly<{ overview: Overview; selected: Selected }>,
) {
  const { node, path } = props.selected;
  const info = node === ARRIVE ? ARRIVAL : props.overview.stations[node];
  const example = props.overview.examples[path];
  const seen = example ? seenHere(node, example, path) : null;
  return (
    <aside className="map-panel" aria-live="polite" aria-label="Station">
      <h3>{info.name}</h3>
      {info.gate && <p className="gate-note">A person decides here.</p>}
      <dl>
        <div>
          <dt>What happens</dt>
          <dd>{info.does}</dd>
        </div>
        <div>
          <dt>What it can't do</dt>
          <dd>{info.cannot}</dd>
        </div>
        {example && seen && (
          <div>
            <dt>In a real ticket</dt>
            <dd>
              {seen} <code>{example.id}</code>
            </dd>
          </div>
        )}
        {node === "enforce" && (
          <div>
            <dt>The rules, in the order they run</dt>
            <dd>
              <ul className="rule-list">
                {props.overview.rules.map((rule) => (
                  <li key={rule.name}>
                    <strong>{rule.name}</strong>: {rule.does}{" "}
                    <code>{rule.code}</code>
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
        <div>
          <dt>Where in the code</dt>
          <dd>
            <code>{info.code}</code>
          </dd>
        </div>
      </dl>
    </aside>
  );
}

function Follow(
  props: Readonly<{
    overview: Overview;
    path: RoutePath;
    onChange: (path: RoutePath) => void;
  }>,
) {
  return (
    <fieldset className="follow">
      <legend>Follow a ticket that took this path</legend>
      {props.overview.lines.map((line) => (
        <label key={line.path} className={`path-${line.path}`}>
          <input
            type="radio"
            name="follow"
            checked={props.path === line.path}
            onChange={() => {
              props.onChange(line.path);
            }}
          />
          {line.label}
        </label>
      ))}
      {!props.overview.examples[props.path] && (
        <p className="quiet">
          The latest development run has no correctly handled ticket on this
          path, so there's no example to follow.
        </p>
      )}
    </fieldset>
  );
}

function Proof({ overview }: Readonly<{ overview: Overview }>) {
  const result = overview.result;
  const goal = overview.goal;
  return (
    <section className="how-section" aria-labelledby="proof">
      <h2 id="proof">How sure we are</h2>
      {result ? (
        <dl className="answers">
          <div>
            <dt>How often does it choose the right path?</dt>
            <dd>
              {percent(result.path_accuracy)}, give or take{" "}
              {(result.path_margin * 100).toFixed(0)} points, on {result.n}{" "}
              development tickets.
            </dd>
          </div>
          <div>
            <dt>Is that better than something simpler?</dt>
            <dd>
              Not yet. A simple classifier trained on the knowledge base gets{" "}
              {percent(result.classifier_path_accuracy)} on the same tickets.
              Beating it is the next experiment.
            </dd>
          </div>
          <div>
            <dt>What does a ticket cost?</dt>
            <dd>
              {rappen(result.cost_per_ticket_chf)} in model calls, and{" "}
              {seconds(result.time_per_ticket_sec)} of the agent's time.
            </dd>
          </div>
          <div>
            <dt>When does it pay off?</dt>
            <dd>
              Once technicians approve more than {percent(goal.break_even)} of
              its decisions: a review takes about {goal.review_minutes} minutes,
              and a first pass by hand about {goal.minutes_by_hand}.
            </dd>
          </div>
        </dl>
      ) : (
        <p className="waiting">
          No evaluation is saved yet. Run <code>uv run -m evals --set dev</code>{" "}
          to measure it.
        </p>
      )}
      {result && (
        <p className="caption">
          From run <code>{result.run}</code> on {result.date.slice(0, 10)}.
          Evaluations has the full breakdown.
        </p>
      )}
    </section>
  );
}

function Model({ overview }: Readonly<{ overview: Overview }>) {
  const model = overview.model;
  const price =
    model.input_usd_per_million === null
      ? "No price on record"
      : `USD ${model.input_usd_per_million.toFixed(2)} in and USD ${(model.output_usd_per_million ?? 0).toFixed(2)} out, per million tokens`;
  return (
    <section className="how-section" aria-labelledby="model">
      <h2 id="model">The model</h2>
      <dl className="answers">
        <div>
          <dt>Which one</dt>
          <dd>
            <code>{model.name}</code>, by Anthropic. {price}.
          </dd>
        </div>
        <div>
          <dt>How it's used</dt>
          <dd>
            {model.calls_per_ticket} call per ticket. {model.how}
          </dd>
        </div>
        <div>
          <dt>Why this one</dt>
          <dd>{model.why}</dd>
        </div>
      </dl>
    </section>
  );
}

function Tools({ overview }: Readonly<{ overview: Overview }>) {
  const groups = [
    {
      title: "Routine",
      rows: overview.tools.filter((t) => t.tier === "routine"),
      means: overview.tiers.routine,
    },
    {
      title: "Sensitive",
      rows: overview.tools.filter((t) => t.tier === "sensitive"),
      means: overview.tiers.sensitive,
    },
  ];
  return (
    <section className="how-section" aria-labelledby="tools">
      <h2 id="tools">The tools it can propose</h2>
      <p className="caption">
        {overview.tools.length} tools, every one simulated. The model only names
        a tool. It runs after a person approves, and code checks the name first.
      </p>
      <div className="table-scroll">
        <table className="tools">
          <thead>
            <tr>
              <th scope="col">Tool</th>
              <th scope="col">What it does</th>
              <th scope="col">Owned by</th>
            </tr>
          </thead>
          {groups.map((group) => (
            <tbody key={group.title}>
              <tr className="group">
                <th colSpan={3} scope="colgroup">
                  {group.title}, {group.rows.length} tools.{" "}
                  <span className="quiet">{group.means}</span>
                </th>
              </tr>
              {group.rows.map((tool) => (
                <tr key={tool.name}>
                  <td>
                    <code>{tool.name}</code>
                  </td>
                  <td>
                    {tool.does}
                    {tool.escalation && (
                      <span className="quiet">
                        {" "}
                        It changes no system: it opens a ticket.
                      </span>
                    )}
                  </td>
                  <td>{tool.owner?.replaceAll("_", " ") ?? "Any team"}</td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  );
}

function Services({ overview }: Readonly<{ overview: Overview }>) {
  return (
    <section className="how-section" aria-labelledby="services">
      <h2 id="services">Where things live</h2>
      <p className="caption">
        Each service has one job, so nothing has two sources of truth.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Service</th>
              <th scope="col">What it holds</th>
              <th scope="col">Source of truth</th>
              <th scope="col">On this machine</th>
            </tr>
          </thead>
          <tbody>
            {overview.services.map((service) => (
              <tr key={service.name}>
                <th scope="row">{service.name}</th>
                <td>{service.holds}</td>
                <td>{service.truth ? "Yes" : "No"}</td>
                <td>
                  {service.connected ? "In use" : "Not set up, memory instead"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Limits({ overview }: Readonly<{ overview: Overview }>) {
  return (
    <section className="how-section" aria-labelledby="limits">
      <h2 id="limits">Where it falls short</h2>
      <ul className="limits">
        {overview.limits.map((limit) => (
          <li key={limit}>{limit}</li>
        ))}
      </ul>
      <p className="caption">
        Versions: instructions{" "}
        <code>{overview.versions.instructions_version}</code>, tools{" "}
        <code>{overview.versions.tools_version}</code>, knowledge base{" "}
        <code>{overview.versions.kb_version}</code>.
      </p>
    </section>
  );
}

/** The same station on the new path, or "Decide" if that path doesn't pass it. */
function stillOnRoute(overview: Overview, node: string, path: RoutePath) {
  const line = overview.lines.find((l) => l.path === path);
  const route = [
    ARRIVE,
    ...overview.trunk,
    ...(line?.stations ?? []),
    ...(line?.otherwise ?? []),
  ];
  return route.includes(node) ? node : "triage";
}

export function HowItWorks() {
  const { data: overview, error } = useLoad(api.overview);
  const [selected, setSelected] = useState<Selected>({
    node: "triage",
    path: "AUTO_FIX",
  });

  if (error) {
    return (
      <p className="notice alert" role="alert">
        {error}
      </p>
    );
  }
  if (!overview) return <p className="waiting">Loading how it works…</p>;

  return (
    <div className="how">
      <section className="how-goal" aria-labelledby="goal">
        <h2 id="goal">{overview.goal.sentence}</h2>
        <p>{overview.goal.worth_it}</p>
      </section>
      <section className="how-route" aria-label="The route">
        <Follow
          overview={overview}
          path={selected.path}
          onChange={(path) => {
            setSelected({
              node: stillOnRoute(overview, selected.node, path),
              path,
            });
          }}
        />
        <div className="map-layout">
          <RouteMap
            overview={overview}
            selected={selected}
            onSelect={setSelected}
          />
          <StationPanel overview={overview} selected={selected} />
        </div>
      </section>
      <Proof overview={overview} />
      <Model overview={overview} />
      <Tools overview={overview} />
      <Services overview={overview} />
      <Limits overview={overview} />
    </div>
  );
}
