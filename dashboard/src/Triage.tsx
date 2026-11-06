import { useEffect, useState, type SyntheticEvent } from "react";
import { api, type Gate, type Run } from "./api";
import { presets } from "./presets";
import { Route } from "./Route";
import { Stats } from "./Stats";
import { useLoad } from "./useLoad";

const RUN_PARAM = "run";

function remember(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set(RUN_PARAM, id);
  else url.searchParams.delete(RUN_PARAM);
  window.history.replaceState(null, "", url);
}

export function Triage() {
  const [text, setText] = useState("");
  const [useRetrieval, setUseRetrieval] = useState(true);
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
    void act(() => api.startTriage(text, useRetrieval));
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
              disabled={busy || noKey || !text.trim()}
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
          <h2>Example tickets</h2>
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
        <section className="result" aria-label="Triage result" aria-busy={busy}>
          {error && (
            <p className="notice alert" role="alert">
              {error}
            </p>
          )}
          {busy && !run && <p className="waiting">Running triage</p>}
          {run ? (
            <Route run={run} busy={busy} onAnswer={answer} />
          ) : (
            !busy && (
              <p className="waiting">
                Pick an example or describe an issue. Its route through triage
                shows here.
              </p>
            )
          )}
        </section>
      </div>
      <Stats refreshKey={run?.pending === null ? run.id : undefined} />
    </>
  );
}
