import { useEffect, useState, type SyntheticEvent } from "react";
import { api, type Gate, type Run } from "./api";
import type { Person } from "./people";
import { presets } from "./presets";
import type { TriageExample as Example } from "./run";
import { Details } from "./Details";
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

/** Tickets to try: real development tickets with their requester, then short ones. */
function Suggestions(
  props: Readonly<{
    examples: Example[] | undefined;
    onPick: (example: Example) => void;
    onPreset: (text: string) => void;
  }>,
) {
  return (
    <div className="suggestions">
      {props.examples && (
        <>
          <h2 id="real-tickets">Real tickets</h2>
          <p className="caption">
            From the development set, with their requester. Their checks were
            recorded, so the agent can read them.
          </p>
          <ul className="chips" aria-label="Real tickets">
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
      )}
      <h2>Short requests</h2>
      <ul className="chips">
        {presets.map((preset) => (
          <li key={preset}>
            <button
              type="button"
              onClick={() => {
                props.onPreset(preset);
              }}
            >
              {preset}
            </button>
          </li>
        ))}
      </ul>
    </div>
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

interface ComposerProps {
  people: Person[] | undefined;
  requester: string;
  onRequester: (id: string) => void;
  text: string;
  onText: (text: string) => void;
  useRetrieval: boolean;
  onRetrieval: (on: boolean) => void;
  blocked: boolean;
  limit: number | undefined;
  onSubmit: (event: SyntheticEvent) => void;
}

/** The message box: the request, who asks, and the switch, beside the button. */
function Composer(props: Readonly<ComposerProps>) {
  return (
    <form className="composer" onSubmit={props.onSubmit}>
      <label htmlFor="ticket" className="sr-only">
        Describe the issue
      </label>
      <textarea
        id="ticket"
        rows={3}
        value={props.text}
        placeholder="My VPN keeps disconnecting since the migration last month"
        onChange={(event) => {
          props.onText(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            props.onSubmit(event);
          }
        }}
      />
      <div className="composer-bar">
        {props.people && (
          <PersonPicker
            people={props.people}
            value={props.requester}
            onChange={props.onRequester}
          />
        )}
        <label className="switch">
          <input
            type="checkbox"
            role="switch"
            checked={props.useRetrieval}
            onChange={(event) => {
              props.onRetrieval(event.target.checked);
            }}
          />
          Use the knowledge base
        </label>
        <span className="composer-send">
          {props.limit !== undefined && (
            <span id="triage-cost" className="cost-note">
              Calls the model, up to about CHF {props.limit.toFixed(2)}
            </span>
          )}
          <button
            type="submit"
            className="primary"
            aria-describedby={
              props.limit === undefined ? undefined : "triage-cost"
            }
            disabled={props.blocked || !props.text.trim() || !props.people}
          >
            Triage this ticket
          </button>
        </span>
      </div>
    </form>
  );
}

/** Above the thread: how to start, or how to start again, and what went wrong. */
function ChatHead(
  props: Readonly<{
    started: boolean;
    working: boolean;
    noKey: boolean;
    error: string | undefined;
    onStartOver: () => void;
  }>,
) {
  return (
    <>
      {props.started ? (
        <div className="chat-head">
          <p>
            One ticket, worked by FirstLine. A new message starts a new ticket.
          </p>
          <button
            type="button"
            onClick={props.onStartOver}
            disabled={props.working}
          >
            New ticket
          </button>
        </div>
      ) : (
        <div className="chat-empty">
          <h2>Describe an IT issue</h2>
          <p>
            FirstLine searches the playbooks, looks up what it needs and
            proposes what to do. Nothing runs until a person confirms.
          </p>
        </div>
      )}
      {props.noKey && (
        <p className="notice alert" role="alert">
          ANTHROPIC_API_KEY isn&apos;t set. Add it to .env and restart the
          backend.
        </p>
      )}
      {props.error && (
        <p className="notice alert" role="alert">
          {props.error}
        </p>
      )}
    </>
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
    if (!text.trim() || busy || working) return;
    // An example's recorded checks belong to it only while it's unchanged.
    const example =
      picked?.text === text && picked.requester === requester
        ? picked.id
        : undefined;
    void act(() => api.startTriage(text, useRetrieval, requester, example));
    setText("");
  }

  function pick(example: Example) {
    setPicked(example);
    setText(example.text);
    setPerson(example.requester);
  }

  function answer(gate: Gate, approved: boolean) {
    if (run) void act(() => api.answerGate(run.id, gate, approved));
  }

  function startOver() {
    setRun(undefined);
    setError(undefined);
    remember(null);
  }

  const noKey = health?.api_key === false;
  const composer = (
    <Composer
      people={people}
      requester={requester}
      onRequester={setPerson}
      text={text}
      onText={setText}
      useRetrieval={useRetrieval}
      onRetrieval={setUseRetrieval}
      blocked={busy || working || noKey}
      limit={health?.assistant_limit_chf}
      onSubmit={submit}
    />
  );

  return (
    <>
      <div className={run ? "assistant has-run" : "assistant"}>
        <section
          className="chat"
          aria-label="Conversation"
          aria-busy={busy || working}
        >
          <ChatHead
            started={Boolean(run)}
            working={working}
            noKey={noKey}
            error={error}
            onStartOver={startOver}
          />
          {busy && !run && <p className="waiting">Starting triage</p>}
          {run && <Thread run={run} busy={busy} onAnswer={answer} />}
          <div className="composer-dock">{composer}</div>
          {!run && (
            <Suggestions examples={examples} onPick={pick} onPreset={setText} />
          )}
        </section>
        {run && <Details run={run} model={health?.model} />}
      </div>
      <Stats refreshKey={run?.pending === null ? run.id : undefined} />
    </>
  );
}
