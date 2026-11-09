import { useCallback, useEffect, useState } from "react";
import { api, type QueueState, type QueueTicket, type QueueView } from "./api";
import { QueueDetail } from "./QueueDetail";
import { pathLabels, rappen, seconds } from "./format";

const POLL_MS = 1000;

const stations: { state: QueueState; label: string }[] = [
  { state: "queued", label: "Queued" },
  { state: "working", label: "Agent working" },
  { state: "review", label: "Waiting for a technician" },
  { state: "closed", label: "Closed" },
];

const verdictLabels = {
  approved: "Approved",
  corrected: "Rerouted",
  rejected: "Rejected",
};

function statusOf(ticket: QueueTicket) {
  if (ticket.review) return verdictLabels[ticket.review.verdict];
  return {
    queued: "Queued",
    working: "Agent working",
    review: "Waiting for review",
    closed: "Closed",
    failed: "Failed",
  }[ticket.state];
}

function Pipeline({ view }: Readonly<{ view: QueueView }>) {
  const shown = view.counts.failed
    ? [...stations, { state: "failed" as const, label: "Failed" }]
    : stations;
  return (
    <ol className="pipeline" aria-label="Tickets by state">
      {shown.map(({ state, label }) => (
        <li key={state} className={`stage stage-${state}`}>
          <span className="stage-dot" aria-hidden="true" />
          <span className="stage-label">{label}</span>
          <span className="stage-count">{view.counts[state]}</span>
        </li>
      ))}
    </ol>
  );
}

function Value({ view }: Readonly<{ view: QueueView }>) {
  const value = view.value;
  return (
    <section className="value" aria-label="How the batch went">
      <dl className="figures">
        <div>
          <dt>Approved unchanged</dt>
          <dd>
            {value.approved} of {value.reviewed}
          </dd>
        </div>
        <div>
          <dt>Review time per ticket</dt>
          <dd>{seconds(value.review_seconds)}</dd>
        </div>
        <div>
          <dt>Agent time per ticket</dt>
          <dd>{seconds(value.agent_seconds)}</dd>
        </div>
        <div>
          <dt>Model cost</dt>
          <dd>{rappen(value.model_cost_chf)}</dd>
        </div>
      </dl>
      <p className="caption">
        What this work is worth in francs, with any mistakes that slipped
        through priced, is under Is it worth it?, Money.
      </p>
    </section>
  );
}

function Decision({ ticket }: Readonly<{ ticket: QueueTicket }>) {
  const decision = ticket.decision;
  if (!decision) {
    return (
      <span className="quiet">
        {ticket.state === "failed" ? "None, see the error" : "Not yet"}
      </span>
    );
  }
  const target = decision.tool ?? decision.queue;
  return (
    <span className={`decision path-${decision.path}`}>
      <span className="path-tag">{pathLabels[decision.path]}</span>
      {target && <code>{target}</code>}
    </span>
  );
}

function TicketList(
  props: Readonly<{
    tickets: QueueTicket[];
    selected?: string;
    onSelect: (id: string) => void;
  }>,
) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Priority</th>
            <th scope="col">Ticket</th>
            <th scope="col">Requester</th>
            <th scope="col">Status</th>
            <th scope="col">Agent's decision</th>
          </tr>
        </thead>
        <tbody>
          {props.tickets.map((ticket) => (
            <tr
              key={ticket.id}
              data-selected={ticket.id === props.selected}
              onClick={() => {
                props.onSelect(ticket.id);
              }}
            >
              <td>{ticket.priority}</td>
              <td className="wide">
                <button
                  type="button"
                  className="link"
                  onClick={() => {
                    props.onSelect(ticket.id);
                  }}
                >
                  {ticket.title}
                </button>
                <small className="ticket-id">{ticket.id}</small>
              </td>
              <td>{ticket.requester.name}</td>
              <td>
                <span
                  className={`chip chip-${ticket.review?.verdict ?? ticket.state}`}
                >
                  {statusOf(ticket)}
                </span>
              </td>
              <td>
                <Decision ticket={ticket} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Queue() {
  const [view, setView] = useState<QueueView>();
  const [selected, setSelected] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const next = await api.queue();
      setView(next);
      return next;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return undefined;
    }
  }, []);

  useEffect(() => {
    let current = true;
    api
      .queue()
      .then((next) => {
        if (current) setView(next);
      })
      .catch((reason: unknown) => {
        if (current) setError(String(reason).replace(/^Error: /, ""));
      });
    return () => {
      current = false;
    };
  }, []);

  const active = view ? view.counts.queued + view.counts.working > 0 : false;
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [active, refresh]);

  async function load() {
    setLoading(true);
    setError(undefined);
    try {
      setView(await api.loadBatch());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  // After a decision, move straight on to the next ticket that needs one.
  async function decided(ticket: QueueTicket) {
    const fresh = await refresh();
    const next = fresh?.tickets.find((t) => t.state === "review");
    setSelected(next?.id ?? ticket.id);
  }

  const current = view?.tickets.find((t) => t.id === selected);

  return (
    <div className="queue">
      <section className="queue-head" aria-label="Service desk">
        <div>
          <h2>Morning queue</h2>
          <p className="caption">
            Tickets arrive from the CorpLabs service desk. The agent proposes a
            decision for each one, and a technician makes the call. Nothing runs
            before that.
          </p>
        </div>
        <div className="load">
          <button
            type="button"
            className="primary"
            disabled={!view || loading || active || view.at_desk === 0}
            onClick={() => void load()}
          >
            {view
              ? `Load ${view.batch_size.toString()} tickets from the service desk`
              : "Load tickets from the service desk"}
          </button>
          {view && (
            <small className="quiet">{view.at_desk} waiting at the desk</small>
          )}
        </div>
      </section>
      {error && (
        <p className="notice alert" role="alert">
          {error}
        </p>
      )}
      {view && (
        <>
          <Pipeline view={view} />
          <Value view={view} />
          {view.tickets.length === 0 ? (
            <p className="waiting">
              The board is empty. Load a batch to watch the agent work through
              it.
            </p>
          ) : (
            <div className="board">
              <TicketList
                tickets={view.tickets}
                selected={selected}
                onSelect={setSelected}
              />
              <aside className="detail" aria-label="Ticket">
                {current ? (
                  <QueueDetail
                    key={current.id}
                    ticket={current}
                    queues={view.queues}
                    onDecided={(ticket) => void decided(ticket)}
                  />
                ) : (
                  <p className="waiting">
                    Choose a ticket to see the agent's work and decide.
                  </p>
                )}
              </aside>
            </div>
          )}
        </>
      )}
    </div>
  );
}
