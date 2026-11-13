import Markdown from "react-markdown";
import type { Gate, Run } from "./api";
import { Handover } from "./Handover";
import { Action } from "./Action";
import { pathLabels } from "./format";
import { Retrieval, RuleNotice } from "./Route";
import { answers, checklist, spent, type Item, type ItemState } from "./steps";

// What each mark means, for a screen reader.
const SAID: Record<ItemState, string> = {
  done: "Done",
  failed: "Failed or refused",
  running: "Working",
  pending: "Still to come",
  rule: "Changed by a rule",
};

function Detail({ item }: Readonly<{ item: Item }>) {
  const step = item.step;
  if (!step) return null;
  return (
    <dl className="step-detail">
      <div>
        <dt>Tool</dt>
        <dd>
          <code>{step.tool}</code>
        </dd>
      </div>
      <div>
        <dt>Input</dt>
        <dd>
          <code>{JSON.stringify(step.input)}</code>
        </dd>
      </div>
    </dl>
  );
}

function Check({ item }: Readonly<{ item: Item }>) {
  const head = (
    <>
      <span className="check-label">{item.label}</span>
      {item.step && <span className="check-spent">{spent(item.step)}</span>}
    </>
  );
  return (
    <li className={`check ${item.state}`}>
      <span className="mark" aria-hidden="true" />
      <span className="sr-only">{SAID[item.state]}: </span>
      {item.step ? (
        <details>
          <summary>{head}</summary>
          <Detail item={item} />
        </details>
      ) : (
        <div className="check-head">{head}</div>
      )}
      {item.result && <p className="check-result">{item.result}</p>}
    </li>
  );
}

/** The agent's steps as stops on one line, which takes the path's colour. */
export function Checklist({ run }: Readonly<{ run: Run }>) {
  const decided = run.status !== "running" && run.path;
  const line = decided ? `path-${run.path}` : "undecided";
  return (
    <ol className={`checklist ${line}`} aria-label="The agent's steps">
      {checklist(run).map((item) => (
        <Check key={item.key} item={item} />
      ))}
    </ol>
  );
}

function Request({ run }: Readonly<{ run: Run }>) {
  const who = run.requester;
  return (
    <div className="message from-person">
      <p className="sender">
        {who.id}, {who.department}, {who.office}
      </p>
      <p className="query">{run.query}</p>
    </div>
  );
}

function Decision({ run }: Readonly<{ run: Run }>) {
  return (
    <div className="decision">
      <p className="path-name">{pathLabels[run.path]}</p>
      {run.rule && <RuleNotice rule={run.rule} />}
      <div className="prose">
        {run.reasoning ? (
          <Markdown>{run.reasoning}</Markdown>
        ) : (
          <p>No reasoning returned.</p>
        )}
      </div>
      <details className="knowledge">
        <summary>Knowledge used</summary>
        <Retrieval run={run} />
      </details>
    </div>
  );
}

/** One ticket as a conversation: the request, the agent's work, and the gates. */
export function Thread(
  props: Readonly<{
    run: Run;
    busy: boolean;
    onAnswer: (gate: Gate, approved: boolean) => void;
  }>,
) {
  const { run } = props;
  const working = run.status === "running";
  const how =
    run.design === "loop"
      ? "Looks things up, then decides"
      : "Decides in one call";
  return (
    <div className="thread">
      <Request run={run} />
      <section
        className={`message from-agent path-${working ? "none" : run.path}`}
        aria-label="FirstLine's reply"
        aria-busy={working}
      >
        <p className="sender">
          <span className="agent-mark" aria-hidden="true">
            FL
          </span>
          FirstLine <span className="design">{working ? "Working" : how}</span>
        </p>
        <Checklist run={run} />
        {!working && run.status !== "failed" && <Decision run={run} />}
      </section>
      {answers(run).map((answer) => (
        <div key={answer.gate} className="message from-person answer">
          <p className="sender">You</p>
          <p>{answer.text}</p>
        </div>
      ))}
      {!working && run.status !== "failed" && (
        <section
          className={run.pending ? "gate-card" : "outcome"}
          aria-label={run.pending ? "Waiting for you" : "What happened"}
        >
          {run.pending && (
            <p className="gate-title">
              <span className="diamond" aria-hidden="true" />
              Waiting for you
            </p>
          )}
          <Action run={run} busy={props.busy} onAnswer={props.onAnswer} />
          {run.handover && run.path === "ESCALATE" && (
            <Handover data={run.handover} />
          )}
        </section>
      )}
    </div>
  );
}
