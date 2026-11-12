import { useEffect, useState, type SyntheticEvent } from "react";
import { api, type Gate, type Run } from "./api";
import type { Person } from "./people";
import { presets } from "./presets";
import type { TriageExample as Example } from "./run";
import { Stats } from "./Stats";
import { Thread } from "./Thread";
import { useLoad } from "./useLoad";

const RUN_PARAM = "run";
const POLL_MS = 1000; // a working run's steps are read again this often
// The rules set's user with two lockouts, so the first try shows SEC-04.
const FIRST_REQUESTER = "s.keller";

function lockouts(n: number) {
  return n === 1
    ? "1 lockout in 24 hours"
    : `${n.toString()} lockouts in 24 hours`;
}

function PersonPicker(
  props: Readonly<{
    people: Person[];
    value: string;
    onChange: (id: string) => void;
  }>,
) {
  const chosen = props.people.find((p) => p.id === props.value);
  const option = (p: Person) => (
    <option key={p.id} value={p.id}>
      {p.name} ({p.id}), {lockouts(p.lockouts_24h)}
    </option>
  );
  return (
    <>
      <label htmlFor="requester">Who is asking</label>
      <select
        id="requester"
        value={props.value}
        onChange={(event) => {
          props.onChange(event.target.value);
        }}
      >
        <optgroup label="Rules set users">
          {props.people.filter((p) => p.rules_set).map(option)}
        </optgroup>
        <optgroup label="Everyone else">
          {props.people.filter((p) => !p.rules_set).map(option)}
        </optgroup>
      </select>
      {chosen && (
        <p className="requester-record" aria-live="polite">
          {chosen.department}, {chosen.office}. {lockouts(chosen.lockouts_24h)}{" "}
          in the records. Device <code>{chosen.device.id}</code>,{" "}
          {chosen.device.model}, image {chosen.device.image}.
        </p>
      )}
    </>
  );
}

function Examples(
  props: Readonly<{ examples: Example[]; onPick: (example: Example) => void }>,
) {
  return (
    <>
      <h2>Real tickets</h2>
      <p className="caption">
        From the development set, with their requester. Their checks were
        recorded, so the agent can read them.
      </p>
      <ul className="presets examples" aria-label="Real tickets">
        {props.examples.map((example) => (
          <li key={example.id}>
            <button
              type="button"
              onClick={() => {
                props.onPick(example);
              }}
            >
              {example.title}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Reads a working run every second, so each step shows as it lands. */
function useLive(
  run: Run | undefined,
  setRun: (run: Run) => void,
  setError: (error: string) => void,
) {
  const working = run?.status === "running";
  const runId = run?.id;
  useEffect(() => {
    if (!working || !runId) return;
    const timer = setInterval(() => {
      api
        .readRun(runId)
        .then(setRun)
        .catch((reason: unknown) => {
          setError(String(reason).replace(/^Error: /, ""));
        });
    }, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [working, runId, setRun, setError]);
  return working;
}

function remember(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set(RUN_PARAM, id);
  else url.searchParams.delete(RUN_PARAM);
  window.history.replaceState(null, "", url);
}

/** The thread, or what to do before there is one. */
function Result(
  props: Readonly<{
    run: Run | undefined;
    busy: boolean;
    error: string | undefined;
    onAnswer: (gate: Gate, approved: boolean) => void;
  }>,
) {
  const { run, busy, error } = props;
  return (
    <section className="result" aria-label="Triage result" aria-busy={busy}>
      {error && (
        <p className="notice alert" role="alert">
          {error}
        </p>
      )}
      {busy && !run && <p className="waiting">Starting triage</p>}
      {run ? (
        <Thread run={run} busy={busy} onAnswer={props.onAnswer} />
      ) : (
        !busy && (
          <p className="waiting">
            Pick an example or describe an issue. The agent&apos;s steps show
            here as it takes them.
          </p>
        )
      )}
    </section>
  );
}

export function Assistant() {
  const [text, setText] = useState("");
  const [useRetrieval, setUseRetrieval] = useState(true);
  const [requester, setPerson] = useState(FIRST_REQUESTER);
  const { data: people } = useLoad(api.requesters);
  const { data: examples } = useLoad(api.examples);
  const [picked, setPicked] = useState<Example>();
  const [run, setRun] = useState<Run>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const { data: health } = useLoad(api.health);

  // A run waiting at a gate is stored by the backend, so a reload finds it again.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get(RUN_PARAM);
    if (id) {
      api
        .readRun(id)
        .then(setRun)
        .catch(() => {
          remember(null);
        });
    }
  }, []);

  const working = useLive(run, setRun, setError);

  async function act(call: () => Promise<Run>) {
    setBusy(true);
    setError(undefined);
    try {
      const next = await call();
      setRun(next);
      remember(next.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    // An example's recorded checks belong to it only while it's unchanged.
    const example =
      picked?.text === text && picked.requester === requester
        ? picked.id
        : undefined;
    void act(() => api.startTriage(text, useRetrieval, requester, example));
  }

  function pick(example: Example) {
    setPicked(example);
    setText(example.text);
    setPerson(example.requester);
  }

  function answer(gate: Gate, approved: boolean) {
    if (run) void act(() => api.answerGate(run.id, gate, approved));
  }

  const noKey = health?.api_key === false;

  return (
    <>
      <div className="triage">
        <section className="intake" aria-label="New ticket">
          <form onSubmit={submit}>
            {people && (
              <PersonPicker
                people={people}
                value={requester}
                onChange={setPerson}
              />
            )}
            <label htmlFor="ticket">Describe the issue</label>
            <textarea
              id="ticket"
              rows={4}
              value={text}
              placeholder="My VPN keeps disconnecting since the migration last month"
              onChange={(event) => {
                setText(event.target.value);
              }}
            />
            <label className="switch">
              <input
                type="checkbox"
                role="switch"
                checked={useRetrieval}
                onChange={(event) => {
                  setUseRetrieval(event.target.checked);
                }}
              />
              Use the knowledge base
            </label>
            <button
              type="submit"
              className="primary"
              disabled={busy || working || noKey || !text.trim() || !people}
            >
              Triage this ticket
            </button>
          </form>
          {noKey && (
            <p className="notice alert" role="alert">
              ANTHROPIC_API_KEY isn't set. Add it to .env and restart the
              backend.
            </p>
          )}
          {examples && <Examples examples={examples} onPick={pick} />}
          <h2>Short requests</h2>
          <ul className="presets">
            {presets.map((preset) => (
              <li key={preset}>
                <button
                  type="button"
                  onClick={() => {
                    setText(preset);
                  }}
                >
                  {preset}
                </button>
              </li>
            ))}
          </ul>
        </section>
        <Result run={run} busy={busy} error={error} onAnswer={answer} />
      </div>
      <Stats refreshKey={run?.pending === null ? run.id : undefined} />
    </>
  );
}
