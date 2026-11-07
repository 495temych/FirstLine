import { useState } from "react";
import { api, type LabelledTicket, type ScoredTicket } from "./api";
import { pathLabels } from "./format";
import { useLoad } from "./useLoad";

const PATHS = ["SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"];
const DIFFICULTIES = ["routine", "hard", "records"];
const LOCKOUT_LIMIT = 2; // SEC-04: this many lockouts in 24 hours is a possible compromise

function Pills(
  props: Readonly<{
    legend: string;
    options: string[];
    value: string | null;
    label?: (option: string) => string;
    onChange: (value: string | null) => void;
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
            props.onChange(props.value === option ? null : option);
          }}
        >
          {props.label ? props.label(option) : option}
        </button>
      ))}
    </fieldset>
  );
}

const target = ({ answer }: LabelledTicket) =>
  [...answer.tools, ...answer.queues].join(", ") || "any";

const expectedPaths = ({ answer }: LabelledTicket) =>
  answer.paths.map((path) => pathLabels[path]).join(" or ");

const headline = (ticket: LabelledTicket) => ticket.text.split("\n")[0];

const unique = (values: string[]) =>
  [...new Set(values)].sort((a, b) => a.localeCompare(b));

function Choice(
  props: Readonly<{
    id: string;
    legend: string;
    options: string[];
    value: string;
    onChange: (value: string) => void;
  }>,
) {
  return (
    <div>
      <label htmlFor={props.id}>{props.legend}</label>
      <select
        id={props.id}
        value={props.value}
        onChange={(event) => {
          props.onChange(event.target.value);
        }}
      >
        <option value="">All</option>
        {props.options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}

function Mark({ result }: Readonly<{ result: ScoredTicket | null }>) {
  if (!result) return <>not run</>;
  return result.action_correct ? (
    <span className="right">Correct</span>
  ) : (
    <span className="wrong">Wrong</span>
  );
}

function agentSentence(result: ScoredTicket | null) {
  if (!result) return "This ticket isn't in a saved evaluation yet.";
  if (result.error) return `The latest run failed with ${result.error}.`;
  const action = result.queue ?? result.tool;
  const chose = [pathLabels[result.path], action].filter(Boolean).join(", ");
  const verdict = result.action_correct ? "Correct" : "Wrong";
  return `${verdict} in the latest run: the agent chose ${chose}.`;
}

function Fact({ name, value }: Readonly<{ name: string; value: string }>) {
  return (
    <div>
      <dt>{name}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Detail({ ticket }: Readonly<{ ticket: LabelledTicket }>) {
  const { answer, requester } = ticket;
  const { device } = requester;
  const lockouts = requester.lockouts_24h;
  return (
    <article className="detail">
      <h2>{headline(ticket)}</h2>
      <p className="caption">
        {ticket.id}, {answer.family}, {answer.difficulty}
      </p>
      {ticket.text !== headline(ticket) && (
        <p>{ticket.text.slice(headline(ticket).length).trim()}</p>
      )}
      <h3>Expected</h3>
      <dl className="facts">
        {answer.cause && <Fact name="Cause" value={answer.cause} />}
        <Fact name="Path" value={expectedPaths(ticket)} />
        <Fact name="Tool or queue" value={target(ticket)} />
        <Fact name="Knowledge base" value={answer.units.join(", ") || "none"} />
        {answer.checks.length > 0 && (
          <Fact name="Required checks" value={answer.checks.join(", ")} />
        )}
        {answer.root_cause && (
          <Fact name="Root cause on record" value={answer.root_cause} />
        )}
        {answer.note && <Fact name="Note" value={answer.note} />}
      </dl>
      <h3>Requester</h3>
      <dl className="facts">
        <Fact name="Name" value={`${requester.name} (${requester.id})`} />
        <Fact
          name="Team"
          value={`${requester.department}, floor ${requester.floor.toString()}`}
        />
        <Fact
          name="Device"
          value={`${device.id}, ${device.model}, image ${device.image}, age ${device.age_years.toString()}, battery ${device.battery_health.toString()}%`}
        />
        <div>
          <dt>Lockouts in 24 hours</dt>
          <dd className={lockouts >= LOCKOUT_LIMIT ? "wrong" : undefined}>
            {lockouts}
          </dd>
        </div>
        <Fact name="Groups" value={requester.groups.join(", ") || "none"} />
        <Fact
          name="Recent tickets"
          value={requester.recent_tickets.join("; ") || "none"}
        />
      </dl>
      <p className="caption">The agent can't see these records yet.</p>
      <p>{agentSentence(ticket.latest)}</p>
    </article>
  );
}

function Browser({ tickets }: Readonly<{ tickets: LabelledTicket[] }>) {
  const [path, setPath] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState<string | null>(null);
  const [family, setFamily] = useState("");
  const [cause, setCause] = useState("");
  const [selected, setSelected] = useState<string>();

  const inFamily = tickets.filter(
    ({ answer }) => family === "" || answer.family === family,
  );
  const causes = unique(
    inFamily.flatMap(({ answer }) => (answer.cause ? [answer.cause] : [])),
  );
  const shown = inFamily.filter(
    ({ answer }) =>
      (cause === "" || answer.cause === cause) &&
      (path === null || answer.paths.includes(path)) &&
      (difficulty === null || answer.difficulty === difficulty),
  );
  const current = shown.find((t) => t.id === selected) ?? shown.at(0);

  return (
    <>
      <div className="filters">
        <Choice
          id="family"
          legend="Family"
          options={unique(tickets.map(({ answer }) => answer.family))}
          value={family}
          onChange={(value) => {
            setFamily(value);
            setCause("");
          }}
        />
        <Choice
          id="cause"
          legend="Cause"
          options={causes}
          value={cause}
          onChange={setCause}
        />
        <Pills
          legend="Path"
          options={PATHS}
          value={path}
          label={(option) => pathLabels[option]}
          onChange={setPath}
        />
        <Pills
          legend="Difficulty"
          options={DIFFICULTIES}
          value={difficulty}
          onChange={setDifficulty}
        />
      </div>
      <p className="caption" role="status">
        {shown.length} of {tickets.length} tickets
      </p>
      {current ? (
        <div className="tickets">
          <div className="table-scroll tall">
            <table>
              <thead>
                <tr>
                  <th scope="col">Ticket</th>
                  <th scope="col">Latest run</th>
                  <th scope="col">Text</th>
                  <th scope="col">Family</th>
                  <th scope="col">Cause</th>
                  <th scope="col">Expected</th>
                  <th scope="col">Tool or queue</th>
                  <th scope="col">Difficulty</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((ticket) => (
                  <tr key={ticket.id} data-selected={ticket === current}>
                    <td>
                      <button
                        type="button"
                        className="link"
                        aria-pressed={ticket === current}
                        onClick={() => {
                          setSelected(ticket.id);
                        }}
                      >
                        {ticket.id}
                      </button>
                    </td>
                    <td>
                      <Mark result={ticket.latest} />
                    </td>
                    <td className="wide">{headline(ticket)}</td>
                    <td>{ticket.answer.family}</td>
                    <td>{ticket.answer.cause ?? "None"}</td>
                    <td>{expectedPaths(ticket)}</td>
                    <td>
                      <code>{target(ticket)}</code>
                    </td>
                    <td>{ticket.answer.difficulty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Detail ticket={current} />
        </div>
      ) : (
        <p className="notice">No tickets match these filters.</p>
      )}
    </>
  );
}

export function Tickets() {
  const { data, error } = useLoad(api.tickets);
  if (error) return <p className="notice alert">{error}</p>;
  if (!data) return null;
  return <Browser tickets={data} />;
}
