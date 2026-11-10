import { useLayoutEffect, useRef, useState } from "react";
import type { QueueState, QueueTicket, Verdict } from "./api";
import { pathLabels, rappen, seconds } from "./format";

/** The board's columns, in the order a ticket moves through them. */
const columns: { state: QueueState; label: string }[] = [
  { state: "queued", label: "Queued" },
  { state: "working", label: "Agent working" },
  { state: "review", label: "Waiting for a technician" },
  { state: "closed", label: "Closed" },
];

const FAILED = { state: "failed" as const, label: "Failed" };

const verdictLabels: Record<Verdict, string> = {
  approved: "Approved",
  corrected: "Rerouted",
  rejected: "Rejected",
};

/** How many closed tickets show before the rest are asked for. */
const CLOSED_SHOWN = 6;

/** Closed tickets, the most recently decided first. */
function byRecent(tickets: QueueTicket[]) {
  const at = (t: QueueTicket) => t.review?.at ?? "";
  return [...tickets].sort((a, b) => at(b).localeCompare(at(a)));
}

function Footer({ ticket }: Readonly<{ ticket: QueueTicket }>) {
  if (ticket.review) {
    const verdict = ticket.review.verdict;
    return (
      <span className={`chip chip-${verdict}`}>{verdictLabels[verdict]}</span>
    );
  }
  if (ticket.state === "failed") {
    return <span className="chip chip-failed">Needs a person</span>;
  }
  if (ticket.state === "working") {
    return <span className="quiet working">The agent is reading it</span>;
  }
  if (ticket.agent_seconds === null) return null;
  return (
    <span className="quiet">
      {seconds(ticket.agent_seconds)}, {rappen(ticket.cost_chf)}
    </span>
  );
}

function Card(
  props: Readonly<{
    ticket: QueueTicket;
    selected: boolean;
    onSelect: (id: string) => void;
    place: (id: string, element: HTMLElement | null) => void;
  }>,
) {
  const { ticket } = props;
  const decision = ticket.decision;
  const target = decision?.tool ?? decision?.queue;
  return (
    <li
      ref={(element) => {
        props.place(ticket.id, element);
      }}
    >
      <button
        type="button"
        className={decision ? `card path-${decision.path}` : "card"}
        aria-pressed={props.selected}
        onClick={() => {
          props.onSelect(ticket.id);
        }}
      >
        <span className="card-meta">
          <span className={`priority priority-${ticket.priority}`}>
            {ticket.priority}
          </span>
          <code>{ticket.id}</code>
        </span>
        <strong className="card-title">{ticket.title}</strong>
        <span className="quiet">{ticket.requester.name}</span>
        {decision && (
          <span className="card-decision">
            <span className="path-tag">{pathLabels[decision.path]}</span>
            {target && <code>{target}</code>}
          </span>
        )}
        <Footer ticket={ticket} />
      </button>
    </li>
  );
}

/** Slides each card from where it was to where it is now, unless the reader
 * asks for less motion. A state change is the only motion on the board. */
function useSlide(tickets: QueueTicket[]) {
  const elements = useRef(new Map<string, HTMLElement>());
  const last = useRef(new Map<string, DOMRect>());
  useLayoutEffect(() => {
    const still =
      typeof window.matchMedia !== "function" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const next = new Map<string, DOMRect>();
    for (const [id, element] of elements.current) {
      const now = element.getBoundingClientRect();
      next.set(id, now);
      const before = last.current.get(id);
      if (still || !before || typeof element.animate !== "function") continue;
      const dx = before.left - now.left;
      const dy = before.top - now.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
      element.animate(
        [
          { transform: `translate(${dx.toString()}px, ${dy.toString()}px)` },
          { transform: "translate(0, 0)" },
        ],
        { duration: 320, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" },
      );
    }
    last.current = next;
  }, [tickets]);
  return (id: string, element: HTMLElement | null) => {
    if (element) elements.current.set(id, element);
    else elements.current.delete(id);
  };
}

export function Board(
  props: Readonly<{
    tickets: QueueTicket[];
    selected?: string;
    onSelect: (id: string) => void;
  }>,
) {
  const place = useSlide(props.tickets);
  const [allClosed, setAllClosed] = useState(false);
  const failed = props.tickets.some((t) => t.state === "failed");
  const shown = failed ? [...columns, FAILED] : columns;
  return (
    <div className="kanban" data-columns={shown.length}>
      {shown.map(({ state, label }) => {
        const inColumn = props.tickets.filter((t) => t.state === state);
        const closed = state === "closed";
        const sorted = closed ? byRecent(inColumn) : inColumn;
        const hidden = closed && !allClosed ? sorted.length - CLOSED_SHOWN : 0;
        const tickets = hidden > 0 ? sorted.slice(0, CLOSED_SHOWN) : sorted;
        const id = `column-${state}`;
        return (
          <section
            key={state}
            className={`column column-${state}`}
            aria-labelledby={id}
          >
            <h3 id={id}>
              <span className="column-dot" aria-hidden="true" />
              <span className="column-label">{label}</span>
              <span className="column-count">{inColumn.length}</span>
            </h3>
            <ol aria-label={`${label}, ${inColumn.length.toString()} tickets`}>
              {tickets.map((ticket) => (
                <Card
                  key={ticket.id}
                  ticket={ticket}
                  selected={ticket.id === props.selected}
                  onSelect={props.onSelect}
                  place={place}
                />
              ))}
            </ol>
            {closed && sorted.length > CLOSED_SHOWN && (
              <button
                type="button"
                className="link"
                onClick={() => {
                  setAllClosed(!allClosed);
                }}
              >
                {allClosed
                  ? "Show the latest only"
                  : `Show ${hidden.toString()} more`}
              </button>
            )}
          </section>
        );
      })}
    </div>
  );
}
