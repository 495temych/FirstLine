import type { DraftTicket, Gate, Run, ToolResult } from "./api";
import { dateTime } from "./format";
import { actionState } from "./gates";

interface Choice {
  gate: Gate;
  yes: string;
  no: string;
  busy: boolean;
  onAnswer: (gate: Gate, approved: boolean) => void;
}

function Choices({ gate, yes, no, busy, onAnswer }: Readonly<Choice>) {
  return (
    <div className="choices">
      <button
        type="button"
        className="primary"
        disabled={busy}
        onClick={() => {
          onAnswer(gate, true);
        }}
      >
        {yes}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          onAnswer(gate, false);
        }}
      >
        {no}
      </button>
    </div>
  );
}

function Facts({ facts }: Readonly<{ facts: [string, string | undefined][] }>) {
  return (
    <dl className="facts">
      {facts.map(([name, value]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function ProposedFix({ run }: Readonly<{ run: Run }>) {
  return (
    <div className="card">
      <h3>Proposed fix</h3>
      <code>{run.tool_name}</code>
      <Facts
        facts={Object.entries(run.tool_input ?? {}).map(([name, value]) => [
          name,
          String(value),
        ])}
      />
    </div>
  );
}

function TicketCard({ ticket }: Readonly<{ ticket: DraftTicket }>) {
  const details: [string, string | undefined][] =
    ticket.source === "decline"
      ? [
          ["Declined fix", ticket.declined_tool],
          ["Reason", ticket.reason],
          ["Diagnosis", ticket.diagnostic_summary],
        ]
      : [["Summary", ticket.summary]];
  return (
    <div className="card">
      <h3>Draft ServiceNow incident</h3>
      <Facts
        facts={[
          ["Queue", ticket.queue],
          ["Priority", ticket.priority],
          ...details,
        ]}
      />
    </div>
  );
}

function Done({
  result,
  title,
}: Readonly<{ result: ToolResult; title: string }>) {
  return (
    <div className="notice good">
      <strong>{title}</strong>
      <p>{result.detail}</p>
      <small>{dateTime(result.timestamp)}</small>
    </div>
  );
}

function TicketDone({ result }: Readonly<{ result: ToolResult }>) {
  return (
    <Done
      result={result}
      title={`Ticket ${result.ticket_number ?? ""} created (simulated)`}
    />
  );
}

function TicketGate({
  run,
  busy,
  onAnswer,
}: Readonly<Pick<Choice, "busy" | "onAnswer"> & { run: Run }>) {
  if (run.pending?.kind !== "confirm_ticket") return null;
  return (
    <>
      <TicketCard ticket={run.pending.ticket} />
      <p className="held">
        Waiting for you. Creating it notifies the on-call technician for{" "}
        {run.pending.ticket.queue}.
      </p>
      <Choices
        gate="confirm_ticket"
        yes="Create ticket"
        no="Don't create ticket"
        busy={busy}
        onAnswer={onAnswer}
      />
    </>
  );
}

export function Action(
  props: Readonly<{
    run: Run;
    busy: boolean;
    onAnswer: (gate: Gate, approved: boolean) => void;
  }>,
) {
  const { run, busy, onAnswer } = props;
  const state = actionState(run);
  const fix = run.path === "AUTO_FIX" && <ProposedFix run={run} />;

  switch (state) {
    case "out_of_scope":
      return <p>Outside IT support, so no action was taken.</p>;
    case "no_tools":
      return (
        <p>
          With the knowledge base off, the agent has no tools and chooses no
          path. Turn it back on to see a grounded answer.
        </p>
      );
    case "await_self_serve":
      return (
        <>
          <p className="held">
            The steps are in the reasoning above. Did they work?
          </p>
          <Choices
            gate="self_serve"
            yes="This resolved it"
            no="It didn't, escalate to a technician"
            busy={busy}
            onAnswer={onAnswer}
          />
        </>
      );
    case "await_fix":
      return (
        <>
          {fix}
          <p className="held">This fix won't run until you confirm it.</p>
          <Choices
            gate="confirm_fix"
            yes="Run fix"
            no="Decline fix"
            busy={busy}
            onAnswer={onAnswer}
          />
        </>
      );
    case "await_ticket":
      return <TicketGate run={run} busy={busy} onAnswer={onAnswer} />;
    case "await_declined_ticket":
      return (
        <>
          {fix}
          <p>
            Fix declined. This ticket is pre-filled from the diagnosis above,
            with no new model call.
          </p>
          <TicketGate run={run} busy={busy} onAnswer={onAnswer} />
        </>
      );
    case "resolved":
      return <p className="notice good">Marked as resolved.</p>;
    case "fix_done":
      return (
        <>
          {fix}
          {run.tool_result && (
            <Done result={run.tool_result} title="Fix ran (simulated)" />
          )}
        </>
      );
    case "ticket_done":
      return (
        <>
          {fix}
          {run.tool_result && <TicketDone result={run.tool_result} />}
        </>
      );
    case "skipped":
      return (
        <>
          {fix}
          <p className="notice">
            {run.path === "AUTO_FIX"
              ? "Fix declined and no ticket created."
              : "No ticket created."}
          </p>
        </>
      );
  }
}
