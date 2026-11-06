import type { ReactNode } from "react";
import Markdown from "react-markdown";
import type { Gate, Run, Unit } from "./api";
import { Action } from "./Action";
import { pathLabels, plainText } from "./format";

function Station(
  props: Readonly<{
    n: number;
    title: string;
    gate?: boolean;
    children: ReactNode;
  }>,
) {
  return (
    <li className={props.gate ? "station gate" : "station"}>
      <span className="stop" aria-hidden="true">
        {props.n}
      </span>
      <h2>{props.title}</h2>
      {props.children}
    </li>
  );
}

function UnitMatch({ unit }: Readonly<{ unit: Unit }>) {
  const label = unit.section ? `${unit.doc}, ${unit.section}` : unit.doc;
  return (
    <div className="unit">
      <details>
        <summary>
          <span>{label}</span>
          <span className="score">{unit.score.toFixed(2)}</span>
        </summary>
        <div className="prose">
          <Markdown>{unit.text}</Markdown>
        </div>
      </details>
      {unit.highlights.length > 0 && (
        <ul className="highlights" aria-label={`Why ${label} matched`}>
          {unit.highlights.map((highlight) => (
            <li key={highlight.text}>
              <span className="score">{highlight.score.toFixed(2)}</span>
              {plainText(highlight.text)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Retrieval({ run }: Readonly<{ run: Run }>) {
  if (run.retrieved.length === 0) {
    return (
      <p>
        {run.use_retrieval
          ? "No knowledge base article matched above the confidence threshold."
          : "The knowledge base is off, so nothing was retrieved."}
      </p>
    );
  }
  const documents = new Set(run.retrieved.map((unit) => unit.doc));
  return (
    <>
      {documents.size > 1 && <p>Matched across {documents.size} documents.</p>}
      {run.retrieved.map((unit) => (
        <UnitMatch key={`${unit.doc}-${unit.section ?? ""}`} unit={unit} />
      ))}
    </>
  );
}

export function Route(
  props: Readonly<{
    run: Run;
    busy: boolean;
    onAnswer: (gate: Gate, approved: boolean) => void;
  }>,
) {
  const { run } = props;
  return (
    <>
      <p className="query">{run.query}</p>
      <ol key={run.id} className={`route path-${run.path}`}>
        <Station n={1} title="Retrieval">
          <Retrieval run={run} />
        </Station>
        <Station n={2} title="Decision">
          <p className="path-name">{pathLabels[run.path]}</p>
        </Station>
        <Station n={3} title="Agent reasoning">
          <div className="prose">
            {run.reasoning ? (
              <Markdown>{run.reasoning}</Markdown>
            ) : (
              <p>No reasoning returned.</p>
            )}
          </div>
        </Station>
        <Station n={4} title="Action" gate={run.pending !== null}>
          <Action run={run} busy={props.busy} onAnswer={props.onAnswer} />
        </Station>
      </ol>
    </>
  );
}
