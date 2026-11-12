import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import {
  api,
  type QueueDecision,
  type QueueTicket,
  type ReviewBody,
} from "./api";
import { dateTime, pathLabels, seconds } from "./format";
import { Station } from "./Route";
import { TraceView } from "./TraceView";

function approveLabel(decision: QueueDecision) {
  switch (decision.path) {
    case "AUTO_FIX":
      return "Approve and run fix";
    case "ESCALATE":
      return `Approve and send to ${decision.queue ?? "the team"}`;
    case "SELF_SERVE":
      return "Approve and send steps";
    default:
      return "Approve and close";
  }
}

function Proposal({ decision }: Readonly<{ decision: QueueDecision }>) {
  if (decision.path === "AUTO_FIX" && decision.tool) {
    return (
      <dl className="facts">
        <div>
          <dt>Fix</dt>
          <dd>
            <code>{decision.tool}</code>
          </dd>
        </div>
        {Object.entries(decision.tool_input ?? {}).map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>
              <code>{value}</code>
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  if (decision.path === "ESCALATE") {
    return (
      <dl className="facts">
        <div>
          <dt>Team</dt>
          <dd>
            <code>{decision.queue}</code>
          </dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>{decision.priority}</dd>
        </div>
        <div>
          <dt>Handover</dt>
          <dd>{decision.summary}</dd>
        </div>
      </dl>
    );
  }
  if (decision.path === "SELF_SERVE") {
    return <p>Send the steps above to the requester.</p>;
  }
  return <p>Close the ticket and tell the requester it isn't IT's to fix.</p>;
}

function ReviewPanel(
  props: Readonly<{
    ticket: QueueTicket;
    decision: QueueDecision;
    queues: string[];
    onDecided: (ticket: QueueTicket) => void;
  }>,
) {
  // When the technician opened this decision, to measure how long it took.
  const opened = useRef(0);
  useEffect(() => {
    opened.current = Date.now();
  }, []);
  const [queue, setQueue] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function decide(body: Omit<ReviewBody, "seconds">) {
    setBusy(true);
    setError(undefined);
    const spent = Math.round((Date.now() - opened.current) / 1000);
    try {
      props.onDecided(
        await api.review(props.ticket.id, { ...body, seconds: spent }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setBusy(false);
    }
  }

  return (
    <div className="review">
      <p className="held">The agent has only proposed this. You decide.</p>
      <div className="choices">
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() => void decide({ verdict: "approved" })}
        >
          {approveLabel(props.decision)}
        </button>
      </div>
      <details>
        <summary>Send to another team</summary>
        <div className="choices">
          <label className="sr-only" htmlFor="queue">
            Team
          </label>
          <select
            id="queue"
            value={queue}
            onChange={(event) => {
              setQueue(event.target.value);
            }}
          >
            <option value="">Choose a team</option>
            {props.queues.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={busy || !queue}
            onClick={() => void decide({ verdict: "corrected", queue })}
          >
            Send to team
          </button>
        </div>
      </details>
      <details>
        <summary>Reject the decision</summary>
        <div className="choices">
          <label className="sr-only" htmlFor="reason">
            Why is it wrong?
          </label>
          <textarea
            id="reason"
            rows={2}
            placeholder="Why is it wrong?"
            value={note}
            onChange={(event) => {
              setNote(event.target.value);
            }}
          />
          <button
            type="button"
            disabled={busy || !note.trim()}
            onClick={() => void decide({ verdict: "rejected", note })}
          >
            Reject and handle by hand
          </button>
        </div>
      </details>
      {error && (
        <p className="notice alert" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function Outcome({ ticket }: Readonly<{ ticket: QueueTicket }>) {
  const review = ticket.review;
  if (!review) return null;
  return (
    <div className="draft">
      <h3>
        {
          {
            approved: "Approved",
            corrected: `Rerouted to ${review.queue ?? ""}`,
            rejected: "Rejected",
          }[review.verdict]
        }
      </h3>
      <p>{review.outcome.detail}</p>
      {review.note && <p>Reason: {review.note}</p>}
      <p className="quiet">
        Decided in {seconds(review.seconds)}, {dateTime(review.at)}. Simulated,
        so nothing real changed.
      </p>
    </div>
  );
}

function Work(
  props: Readonly<{
    ticket: QueueTicket;
    decision: QueueDecision;
    queues: string[];
    onDecided: (ticket: QueueTicket) => void;
  }>,
) {
  const { ticket, decision } = props;
  return (
    <ol className={`route path-${decision.path}`}>
      <Station n={1} title="Knowledge used">
        {decision.retrieved.length === 0 ? (
          <p>Nothing in the knowledge base matched with confidence.</p>
        ) : (
          <ul className="sources">
            {decision.retrieved.map((unit) => (
              <li key={`${unit.doc}-${unit.section ?? ""}`}>
                <span>
                  {unit.section ? `${unit.doc}, ${unit.section}` : unit.doc}
                </span>
                <span className="score">{unit.score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </Station>
      <Station n={2} title="Decision">
        <p className="path-name">{pathLabels[decision.path]}</p>
        <p>Likely cause: {decision.cause}</p>
      </Station>
      <Station n={3} title="Reasoning">
        <div className="prose">
          <Markdown>{decision.reasoning || "No reasoning returned."}</Markdown>
        </div>
      </Station>
      <Station n={4} title="Proposed action">
        <Proposal decision={decision} />
      </Station>
      <Station n={5} title="Technician" gate={ticket.state === "review"}>
        {ticket.state === "review" ? (
          <ReviewPanel
            ticket={ticket}
            decision={decision}
            queues={props.queues}
            onDecided={props.onDecided}
          />
        ) : (
          <Outcome ticket={ticket} />
        )}
      </Station>
    </ol>
  );
}

export function QueueDetail(
  props: Readonly<{
    ticket: QueueTicket;
    queues: string[];
    onDecided: (ticket: QueueTicket) => void;
  }>,
) {
  const { ticket } = props;
  return (
    <>
      <header className="ticket-head">
        <h3>{ticket.title}</h3>
        <p className="quiet">
          <code>{ticket.id}</code> · {ticket.priority} priority ·{" "}
          {ticket.sla_plan} · {dateTime(ticket.submitted_at)}
        </p>
      </header>
      <dl className="facts">
        <div>
          <dt>Requester</dt>
          <dd>
            {ticket.requester.name}
            {ticket.requester.department && `, ${ticket.requester.department}`}
            {ticket.requester.office && `, ${ticket.requester.office}`}
          </dd>
        </div>
        {ticket.requester.device && (
          <div>
            <dt>Device</dt>
            <dd>
              <code>{ticket.requester.device}</code>
            </dd>
          </div>
        )}
        {ticket.applications.length > 0 && (
          <div>
            <dt>Applications</dt>
            <dd>{ticket.applications.join(", ")}</dd>
          </div>
        )}
      </dl>
      <details className="ticket-text">
        <summary>Ticket text</summary>
        <p>{ticket.description}</p>
      </details>
      {ticket.state === "queued" && (
        <p className="waiting">Queued. The agent will pick it up next.</p>
      )}
      {ticket.state === "working" && (
        <p className="waiting">The agent is working on this ticket.</p>
      )}
      {ticket.state === "failed" && (
        <p className="notice alert" role="alert">
          The agent couldn't finish: {ticket.error}. A technician takes this one
          by hand.
        </p>
      )}
      {ticket.decision && (
        <Work
          ticket={ticket}
          decision={ticket.decision}
          queues={props.queues}
          onDecided={props.onDecided}
        />
      )}
      {ticket.decision && (
        <TraceView ticketId={ticket.id} cost={ticket.cost_chf} />
      )}
    </>
  );
}
