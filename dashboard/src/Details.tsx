import type { ReactNode } from "react";
import type { Run, RunStatus } from "./api";
import { pathLabels, rappen, seconds } from "./format";

const STATUS: Record<RunStatus, string> = {
  running: "Working",
  waiting: "Waiting for you",
  done: "Done",
  failed: "Failed",
};

/** A path or status as a small tinted label, named in words, not colour alone. */
export function Lozenge(
  props: Readonly<{ kind: string; children: ReactNode }>,
) {
  return <span className={`lozenge ${props.kind}`}>{props.children}</span>;
}

function Row(props: Readonly<{ name: string; children: ReactNode }>) {
  return (
    <div>
      <dt>{props.name}</dt>
      <dd>{props.children}</dd>
    </div>
  );
}

/** What the agent proposes to do: the fix it would run, or the queue it would ask. */
function action(run: Run): ReactNode {
  const queue = run.tool_input?.queue;
  const priority = run.tool_input?.priority;
  if (run.path === "ESCALATE" && typeof queue === "string") {
    return (
      <>
        <code>{queue}</code>
        {typeof priority === "string" && `, ${priority}`}
      </>
    );
  }
  return run.tool_name ? <code>{run.tool_name}</code> : <>None</>;
}

/** The steps the decision rests on, and any it cited that never ran. */
function citedSteps(c: { kept: string[]; dropped: string[] }): string {
  const kept = c.kept.length > 0 ? `Steps ${c.kept.join(", ")}` : "No step";
  if (c.dropped.length === 0) return kept;
  return `${kept}. Dropped ${c.dropped.join(", ")}, which never ran`;
}

/** The ticket's facts beside the conversation, as a Jira issue keeps them. */
export function Details(
  props: Readonly<{ run: Run; model: string | undefined }>,
) {
  const { run } = props;
  const lookups = run.steps.filter((s) => s.tool !== "record_decision").length;
  const decided = Boolean(run.path) && run.status !== "running";
  return (
    <aside className="details" aria-label="Ticket details">
      <h2>Details</h2>
      <dl>
        <Row name="Status">
          <Lozenge kind={`status-${run.status}`}>{STATUS[run.status]}</Lozenge>
        </Row>
        <Row name="Path">
          {decided ? (
            <Lozenge kind={`path-${run.path}`}>{pathLabels[run.path]}</Lozenge>
          ) : (
            "Not decided yet"
          )}
        </Row>
        {decided && run.cause && <Row name="Cause">{run.cause}</Row>}
        {decided && <Row name="Action">{action(run)}</Row>}
        <Row name="Rule">
          {run.rule ? (
            <span className="rule-name">{run.rule.rule} changed it</span>
          ) : (
            "None changed it"
          )}
        </Row>
        <Row name="Requester">
          {run.requester.id}
          <span className="detail-sub">
            {run.requester.department}, {run.requester.office}
          </span>
        </Row>
        <Row name="Lookups">
          {run.design === "loop" ? lookups : "None, it decides in one call"}
        </Row>
        {run.citations && <Row name="Cited">{citedSteps(run.citations)}</Row>}
        <Row name="Time">
          {run.response_time_sec ? seconds(run.response_time_sec) : "n/a"}
        </Row>
        <Row name="Cost">{rappen(run.cost_chf)}</Row>
        {props.model && <Row name="Model">{props.model}</Row>}
        <Row name="Knowledge base">
          {run.use_retrieval ? "On" : "Off for this ticket"}
        </Row>
      </dl>
    </aside>
  );
}
