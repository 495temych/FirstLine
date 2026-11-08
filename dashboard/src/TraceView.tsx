import { useEffect, useState } from "react";
import { api, type Trace, type TraceStep } from "./api";
import { rappen } from "./format";

const RETRY_MS = 2000;
const RETRIES = 15; // Langfuse takes a few seconds to take in a trace

const labels: Record<string, string> = {
  queue: "Whole ticket",
  LangGraph: "Agent run",
  retrieve: "Search the knowledge base",
  triage: "Decide",
  ChatAnthropic: "Model call",
  confirm_fix: "Hold for the technician",
  confirm_ticket: "Hold for the technician",
  self_serve_wait: "Hold for the technician",
};

function Step({ step, total }: Readonly<{ step: TraceStep; total: number }>) {
  const left = (step.start_ms / total) * 100;
  const width = Math.max((step.duration_ms / total) * 100, 0.5);
  return (
    <li className={step.type === "GENERATION" ? "generation" : undefined}>
      <span className="step-name">
        {labels[step.name] ?? step.name}
        {step.model && <small>{step.model}</small>}
      </span>
      <span className="track" aria-hidden="true">
        <span
          className="bar"
          style={{ left: `${left.toString()}%`, width: `${width.toString()}%` }}
        />
      </span>
      <span className="ms">{(step.duration_ms / 1000).toFixed(2)} s</span>
      {step.input_tokens !== null && (
        <small className="usage">
          {step.input_tokens.toLocaleString("de-CH")} tokens in,{" "}
          {(step.output_tokens ?? 0).toLocaleString("de-CH")} out
          {step.cost_usd !== null && `, $${step.cost_usd.toFixed(4)}`}
        </small>
      )}
    </li>
  );
}

export function TraceView(
  props: Readonly<{ ticketId: string; cost: number | null }>,
) {
  const [trace, setTrace] = useState<Trace>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let tries = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let current = true;
    async function read() {
      try {
        const next = await api.trace(props.ticketId);
        if (!current) return;
        setTrace(next);
        tries += 1;
        if (next.status === "pending" && tries < RETRIES) {
          timer = setTimeout(() => void read(), RETRY_MS);
        }
      } catch (reason) {
        if (current) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      }
    }
    void read();
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [props.ticketId]);

  const total = Math.max(
    1,
    ...(trace?.steps ?? []).map((s) => s.start_ms + s.duration_ms),
  );

  return (
    <section className="trace" aria-label="Trace">
      <h3>Trace</h3>
      {error && <p className="notice alert">{error}</p>}
      {trace?.status === "off" && (
        <p className="quiet">
          Tracing is off. Add the Langfuse keys to .env to see each step.
        </p>
      )}
      {trace?.status === "pending" && (
        <p className="waiting">Waiting for Langfuse to receive the trace.</p>
      )}
      {trace?.status === "ready" && (
        <>
          <ol className="timeline">
            {trace.steps.map((step) => (
              <Step
                key={`${step.name}-${step.start_ms.toString()}`}
                step={step}
                total={total}
              />
            ))}
          </ol>
          <p className="quiet">
            {(total / 1000).toFixed(1)} s in all, model cost{" "}
            {rappen(props.cost)}. Personal details were masked before the trace
            left this machine.
          </p>
        </>
      )}
      {trace?.url && (
        <a href={trace.url} target="_blank" rel="noreferrer">
          Open the full trace in Langfuse
        </a>
      )}
    </section>
  );
}
