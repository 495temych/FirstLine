import { useCallback, useState, type ReactNode } from "react";
import { api } from "./api";
import { pathLabels } from "./format";
import type { Harness as HarnessData, HarnessTicket } from "./harnessData";
import { useLoad } from "./useLoad";

const score = (value: number) => value.toFixed(2);

/** One station on the call's route: its name, who acts there, and what happens. */
function Station(
  props: Readonly<{
    name: string;
    who: string;
    gate?: boolean;
    aside?: ReactNode;
    children: ReactNode;
  }>,
) {
  return (
    <li className={props.gate ? "call-stop gate" : "call-stop"}>
      <span className="call-dot" aria-hidden="true" />
      <div className="call-body">
        <h3>
          {props.name} <span className="call-who">{props.who}</span>
        </h3>
        {props.children}
      </div>
      {props.aside}
    </li>
  );
}

function Search({ data }: Readonly<{ data: HarnessData }>) {
  const s = data.search;
  return (
    <p>
      <code>{s.embedding_model}</code> scores every knowledge base section
      against the ticket. A playbook counts when its best section scores{" "}
      {score(s.sure)} or more, or {score(s.threshold)} and {score(s.margin)}{" "}
      ahead of the next. Policies and references must reach {score(s.support)},
      and at most {s.top_k} results go in. It runs on this machine, for free.
    </p>
  );
}

function Reads({
  data,
  ticket,
}: Readonly<{ data: HarnessData; ticket?: HarnessTicket }>) {
  return (
    <ol className="call-reads">
      {data.reads.map((r) => (
        <li key={r.name}>
          <span className="call-role">{r.role}</span>
          <div>
            <strong>{r.name}</strong>
            {r.name === "Instructions" && (
              <span className="quiet">
                {" "}
                {data.instructions.words} words,{" "}
                {data.instructions.sections.length} parts
              </span>
            )}
            {r.name === "The fixes it may propose" && (
              <span className="quiet">
                {" "}
                {data.fixes}, listed under <a href="?view=workflow">Workflow</a>
              </span>
            )}
            <p>{r.what}</p>
            {r.name === "What search found" && ticket && (
              <Found ticket={ticket} />
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function Found({ ticket }: Readonly<{ ticket: HarnessTicket }>) {
  if (ticket.found.length === 0) {
    return <p className="quiet">For this ticket: no clear match.</p>;
  }
  return (
    <ul className="call-found" aria-label="Found for this ticket">
      {ticket.found.map((f) => (
        <li key={f.doc}>
          <code>{f.doc}</code> <span className="quiet">{f.kind}</span>{" "}
          {score(f.score)}
        </li>
      ))}
    </ul>
  );
}

function Model({ data }: Readonly<{ data: HarnessData }>) {
  const m = data.model;
  const via = m.provider ? `${m.lab}, pinned to ${m.provider}` : m.lab;
  return (
    <dl className="call-facts">
      <dt>Model</dt>
      <dd>
        {m.label} <span className="quiet">through {via}</span>
      </dd>
      <dt>Where</dt>
      <dd>{m.region}</dd>
      <dt>Reasoning effort</dt>
      <dd>{m.effort ?? "the model's default"}</dd>
      <dt>Answer limit</dt>
      <dd>{m.max_tokens.toLocaleString("de-CH")} tokens</dd>
      <dt>Tries</dt>
      <dd>up to {m.attempts}, when the provider fails</dd>
      <dt>Its one tool</dt>
      <dd>
        <code>{data.tool.name}</code>,{" "}
        {m.forced ? "which it must call" : "offered but not forced"}
      </dd>
    </dl>
  );
}

function Loop({ data }: Readonly<{ data: HarnessData }>) {
  return (
    <aside className="call-loop" aria-label="The loop">
      <p>
        <strong>No loop yet.</strong> {data.loop.calls} call per ticket.
      </p>
      <p className="quiet">{data.loop.text}</p>
    </aside>
  );
}

function Form({
  data,
  ticket,
}: Readonly<{ data: HarnessData; ticket?: HarnessTicket }>) {
  const a = ticket?.answer;
  const filled: Record<string, string | null | undefined> = {
    path: a && pathLabels[a.path],
    cause: a?.cause,
    tool: a?.tool,
    queue: a?.queue,
  };
  return (
    <ol className="call-form">
      {data.tool.fields.map((f) => (
        <li key={f.name}>
          <code>{f.name}</code>
          {f.required && <span className="quiet"> required</span>}
          <span>{f.means}</span>
          {f.choices && f.name !== "path" && (
            <span className="quiet">One of {f.choices.length}.</span>
          )}
          {filled[f.name] && (
            <span className="call-filled">{filled[f.name]}</span>
          )}
        </li>
      ))}
    </ol>
  );
}

function Checks({ data }: Readonly<{ data: HarnessData }>) {
  return (
    <ul className="call-checks">
      {data.checks.map((c) => (
        <li key={c.when}>
          <strong>{c.when}.</strong> {c.then}{" "}
          <span className="quiet">{c.code}</span>
        </li>
      ))}
    </ul>
  );
}

function Verdict({ ticket }: Readonly<{ ticket: HarnessTicket }>) {
  const a = ticket.answer;
  const expected = a.expected.map((p) => pathLabels[p]).join(" or ");
  const outcome = a.right ? "Right" : "Wrong";
  return (
    <p className={a.right ? "verdict right" : "verdict wrong"}>
      {a.invalid
        ? "The answer didn't fit the form, so it went to a person."
        : `${outcome} in full: the labels expect ${expected}.`}{" "}
      <span className="quiet">
        From run <code>{ticket.run}</code>.
      </span>
    </p>
  );
}

function Follow({
  data,
  chosen,
  onChoose,
}: Readonly<{
  data: HarnessData;
  chosen: string;
  onChoose: (id: string) => void;
}>) {
  return (
    <div className="follow-ticket">
      <label htmlFor="harness-ticket">Follow a development ticket</label>
      <select
        id="harness-ticket"
        value={chosen}
        onChange={(event) => {
          onChoose(event.target.value);
        }}
      >
        {data.examples.map((e) => (
          <option key={e.id} value={e.id}>
            {e.id}: {e.title}
          </option>
        ))}
      </select>
      <p className="quiet">
        Search runs again on this machine, for free. The answer is the one saved
        from the default model&apos;s latest run, so no model is called.
      </p>
    </div>
  );
}

function Call({
  data,
  ticket,
}: Readonly<{ data: HarnessData; ticket?: HarnessTicket }>) {
  return (
    <ol
      className="call"
      aria-label="One ticket's model call, station by station"
    >
      <Station name="Search" who="code, before the model">
        <Search data={data} />
      </Station>
      <Station name="What it reads" who="in this order">
        <Reads data={data} ticket={ticket} />
      </Station>
      <Station name="One call" who="the model" aside={<Loop data={data} />}>
        <Model data={data} />
      </Station>
      <Station name={`The form: ${data.tool.name}`} who="the model fills it in">
        <p>{data.tool.description} Its fields, in the order it fills them:</p>
        <Form data={data} ticket={ticket} />
        {ticket && <Verdict ticket={ticket} />}
      </Station>
      <Station name="Checks on the answer" who="code">
        <Checks data={data} />
      </Station>
      <Station name="A person decides" who="before anything runs" gate>
        <p>
          {data.gates.join(", ")}. What follows each path is on{" "}
          <a href="?view=workflow">Workflow</a>.
        </p>
      </Station>
    </ol>
  );
}

function Exact({
  data,
  ticket,
}: Readonly<{ data: HarnessData; ticket?: HarnessTicket }>) {
  return (
    <>
      <details className="exact">
        <summary>The instructions, as the model reads them</summary>
        <pre>{data.instructions.text}</pre>
      </details>
      {ticket && (
        <details className="exact">
          <summary>The ticket and what search found, exactly as sent</summary>
          <pre>{ticket.message}</pre>
        </details>
      )}
    </>
  );
}

export function Harness() {
  const { data, error } = useLoad(api.harness);
  const [chosen, setChosen] = useState<string>();
  const id = chosen ?? data?.examples[0]?.id;
  const load = useCallback(
    () => (id ? api.harnessTicket(id) : Promise.resolve(undefined)),
    [id],
  );
  const { data: ticket } = useLoad(load, id);
  if (error) {
    return (
      <p className="notice alert" role="alert">
        {error}
      </p>
    );
  }
  if (!data) return null;
  const shown = ticket?.id === id ? ticket : undefined;
  return (
    <div className="how harness">
      <section className="how-goal" aria-labelledby="harness-answer">
        <h2 id="harness-answer">{data.answer}</h2>
      </section>
      {id ? (
        <Follow data={data} chosen={id} onChoose={setChosen} />
      ) : (
        <p className="notice">
          No saved development run of the default model yet. Run{" "}
          <code>uv run -m evals --set dev</code> to follow a real ticket.
        </p>
      )}
      <Call data={data} ticket={shown} />
      <Exact data={data} ticket={shown} />
    </div>
  );
}
