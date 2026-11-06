import { useState } from "react";
import { api, type Stats as StatsData } from "./api";
import { pathLabels } from "./format";
import { useLoad } from "./useLoad";

function Figures({ stats }: Readonly<{ stats: StatsData }>) {
  const rate = stats.automation_rate;
  return (
    <>
      {stats.low_sample && (
        <p className="notice">
          Only {stats.n} logged, too few for a stable rate. Treat these numbers
          as illustrative.
        </p>
      )}
      <dl className="figures">
        <div>
          <dt>Logged tickets</dt>
          <dd>{stats.n}</dd>
        </div>
        <div>
          <dt>Resolved without a technician</dt>
          <dd>{rate === null ? "n/a" : `${rate.toFixed(0)}%`}</dd>
        </div>
      </dl>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Path</th>
              <th scope="col">Tickets</th>
              <th scope="col">Share</th>
              <th scope="col">Average response</th>
            </tr>
          </thead>
          <tbody>
            {stats.paths.map((path) => {
              const seconds = stats.avg_response_time_sec[path];
              return (
                <tr key={path}>
                  <td>{pathLabels[path]}</td>
                  <td>{stats.counts[path]}</td>
                  <td>{stats.pct[path].toFixed(0)}%</td>
                  <td>{seconds == null ? "n/a" : `${seconds.toFixed(2)} s`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="caption">
        Response time covers the agent's decision, not the whole fix, so it's a
        stand-in for time to resolution.
      </p>
    </>
  );
}

export function Stats({ refreshKey }: Readonly<{ refreshKey?: string }>) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="stats"
      onToggle={(event) => {
        setOpen(event.currentTarget.open);
      }}
    >
      <summary>Live usage statistics</summary>
      <p className="caption">
        Real use of this app, read from logs.csv. This isn't an evaluation.
      </p>
      {open && <Live refreshKey={refreshKey} />}
    </details>
  );
}

function Live({ refreshKey }: Readonly<{ refreshKey?: string }>) {
  const { data, error } = useLoad(api.stats, refreshKey);
  if (error) return <p className="notice alert">{error}</p>;
  if (!data) return null;
  if (data.n === 0) {
    return <p>No tickets logged yet. Finish a triage to start the log.</p>;
  }
  return <Figures stats={data} />;
}
