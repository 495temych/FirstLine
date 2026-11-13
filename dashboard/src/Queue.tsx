import { useCallback, useEffect, useState } from "react";
import { api, type QueueTicket, type QueueView } from "./api";
import { QueueDetail } from "./QueueDetail";
import { francs, rappen, seconds } from "./format";
import { Board } from "./QueueBoard";

const POLL_MS = 1000;

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
            <small className="quiet">
              {view.at_desk} waiting at the desk.{" "}
              {view.batch_estimate_chf === null
                ? "This model has no price, so a batch can't start."
                : `About ${francs(view.batch_estimate_chf)} in model calls, capped at ${francs(view.batch_cap_chf)}.`}
            </small>
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
          <Value view={view} />
          {view.tickets.length === 0 ? (
            <p className="waiting">
              The board is empty. Load a batch to watch the agent work through
              it.
            </p>
          ) : (
            <div className={current ? "board open" : "board"}>
              <div className="board-main">
                {!current && (
                  <p className="caption">
                    Choose a ticket to see the agent&apos;s work and decide.
                  </p>
                )}
                <Board
                  tickets={view.tickets}
                  selected={selected}
                  onSelect={setSelected}
                />
              </div>
              {current && (
                <aside className="detail drawer" aria-label="Ticket">
                  <button
                    type="button"
                    className="link close"
                    onClick={() => {
                      setSelected(undefined);
                    }}
                  >
                    Close
                  </button>
                  <QueueDetail
                    key={current.id}
                    ticket={current}
                    queues={view.queues}
                    onDecided={(ticket) => void decided(ticket)}
                  />
                </aside>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
