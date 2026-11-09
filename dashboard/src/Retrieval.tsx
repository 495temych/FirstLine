import { useState } from "react";
import {
  api,
  type Measure,
  type RetrievalTicket,
  type RetrievalView,
  type ScoredSet,
  type SearchResult,
} from "./api";
import { dateTime, francs, percent, plainText, rate } from "./format";
import { points } from "./points";
import { ScoreBars, ScoreChart } from "./ScoreChart";
import { useLoad } from "./useLoad";

type Rule = RetrievalView["rule"];
const two = (n: number) => n.toFixed(2);

const MEASURES: { key: Measure; name: string; set: "dev" | "unseen_dev" }[] = [
  { key: "hit_rate", name: "Hit rate", set: "dev" },
  { key: "mean_reciprocal_rank", name: "Reciprocal rank", set: "dev" },
  { key: "recall", name: "Recall", set: "dev" },
  { key: "false_match_rate", name: "False matches", set: "unseen_dev" },
];

/** How a measure moved across the saved scores of its set, oldest first. */
function moved(view: RetrievalView, key: Measure, set: string) {
  const values = view.history
    .filter((h) => h.set === set)
    .map((h) => h.summary[key])
    .filter((v): v is number => v !== null && v !== undefined);
  if (values.length === 0) return "Not measured before";
  if (values.every((v) => v === values[0])) {
    return `${rate(values[0])} in the ${values.length.toString()} saved scores that measured it`;
  }
  return values.map((v) => rate(v)).join(" → ");
}

function Lede({ view }: Readonly<{ view: RetrievalView }>) {
  const dev = view.sets.dev?.summary;
  const unseen = view.sets.unseen_dev?.summary;
  const hits = Math.round((dev?.hit_rate ?? 0) * (dev?.covered ?? 0));
  const quiet = Math.round(
    (1 - (unseen?.false_match_rate ?? 0)) * (unseen?.uncovered ?? 0),
  );
  return (
    <section className="how-goal" aria-labelledby="lede">
      <h2 id="lede">
        Search finds the right playbook for {hits} of {dev?.covered ?? 0}{" "}
        development tickets.
      </h2>
      <p>
        For {quiet} of {unseen?.uncovered ?? 0} tickets from families with no
        playbook, it correctly finds none. Each ticket is embedded with{" "}
        <code>{view.embedding_model}</code> on this machine and compared with
        every section of the knowledge base, so no model is called and every
        number here is free to recompute.
      </p>
    </section>
  );
}

function Measures({ view }: Readonly<{ view: RetrievalView }>) {
  return (
    <section className="how-section" aria-labelledby="measures">
      <h2 id="measures">The four measures</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {["Question", "Measure", "Now", "Tickets", "Floor", "Before"].map(
                (name) => (
                  <th key={name} scope="col">
                    {name}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {MEASURES.map(({ key, name, set }) => {
              const summary = view.sets[set]?.summary;
              const floor = view.floors[key];
              const n = set === "dev" ? summary?.covered : summary?.uncovered;
              return (
                <tr key={key}>
                  <td>{view.questions[key]}</td>
                  <th scope="row">{name}</th>
                  <td>{rate(summary?.[key])}</td>
                  <td>{n ?? 0}</td>
                  <td>
                    {floor === undefined
                      ? "None yet"
                      : `${percent(floor)}, or the check fails`}
                  </td>
                  <td>{moved(view, key, set)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="caption">
        Hit rate, reciprocal rank and recall use the development tickets, whose
        family has a playbook. False matches use the unseen families, which have
        none. Knowledge base <code>{view.kb_version}</code>.
      </p>
    </section>
  );
}

function outcome(ticket: RetrievalTicket) {
  if (ticket.expected === null) {
    return ticket.top
      ? `It matched ${ticket.top}, though this family has no playbook.`
      : "It matched nothing, as it should: this family has no playbook.";
  }
  if (ticket.hit) return `It found ${ticket.expected}, its family's playbook.`;
  return ticket.top
    ? `It found ${ticket.top} instead of ${ticket.expected}.`
    : `It found nothing, though ${ticket.expected} should match.`;
}

function TicketPanel({
  ticket,
  rule,
}: Readonly<{ ticket: RetrievalTicket; rule: Rule }>) {
  return (
    <aside className="ticket-panel" aria-live="polite" aria-label="Ticket">
      <p className="quiet">
        <code>{ticket.id}</code>
      </p>
      <h3>{ticket.title}</h3>
      <p>{outcome(ticket)}</p>
      <ScoreBars
        ranked={ticket.ranked}
        rule={rule}
        expected={ticket.expected}
      />
      {ticket.also.length > 0 && (
        <p className="caption">
          With it, the agent gets{" "}
          {ticket.also
            .map((unit) => `${unit.doc} (${unit.kind}, ${two(unit.score)})`)
            .join(" and ")}
          .
        </p>
      )}
    </aside>
  );
}

function gapSentence(view: RetrievalView) {
  const dev = view.sets.dev?.tickets ?? [];
  const unseen = view.sets.unseen_dev?.tickets ?? [];
  const right = dev.flatMap((t) =>
    t.right_score === null ? [] : [t.right_score],
  );
  const quiet = unseen.flatMap((t) => {
    const best = t.ranked.at(0);
    return best ? [best.score] : [];
  });
  if (right.length === 0 || quiet.length === 0) return null;
  const weakest = Math.min(...right);
  const strongest = Math.max(...quiet);
  const over = quiet.filter((s) => s >= view.rule.sure).length;
  return (
    `The weakest right match scores ${two(weakest)}, and the strongest score from a family with no playbook is ${two(strongest)}. ` +
    (over > 0
      ? `${over.toString()} of those clear the ${two(view.rule.sure)} bar, so they are false matches.`
      : `None clears the ${two(view.rule.sure)} bar.`)
  );
}

function TicketTable({
  sets,
  onSelect,
}: Readonly<{
  sets: (ScoredSet | null)[];
  onSelect: (id: string) => void;
}>) {
  const tickets = sets.flatMap((set) => set?.tickets ?? []);
  return (
    <details>
      <summary>The {tickets.length} tickets as a table</summary>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {["Ticket", "Should match", "Found", "Score"].map((name) => (
                <th key={name} scope="col">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id}>
                <td>
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      onSelect(t.id);
                    }}
                  >
                    {t.id}
                  </button>{" "}
                  {t.title}
                </td>
                <td>{t.expected ?? "Nothing"}</td>
                <td>{t.top ?? "Nothing"}</td>
                <td>{t.score === null ? "n/a" : two(t.score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function WhyTheBar({ view }: Readonly<{ view: RetrievalView }>) {
  const all = points(view.sets.dev, view.sets.unseen_dev);
  const [chosen, setChosen] = useState<string | null>(
    all.find((p) => p.wrong)?.ticket.id ?? all.at(0)?.ticket.id ?? null,
  );
  const ticket = [view.sets.dev, view.sets.unseen_dev]
    .flatMap((set) => set?.tickets ?? [])
    .find((t) => t.id === chosen);
  const { sure, threshold, margin } = view.rule;
  return (
    <section className="how-section" aria-labelledby="why-bar">
      <h2 id="why-bar">Why the bar sits where it does</h2>
      <p>
        A playbook counts as a match when it scores {two(sure)} or more, or when
        it scores {two(threshold)} or more and beats the next by {two(margin)}.
        The shaded area is where that holds. {gapSentence(view)}
      </p>
      <ul className="legend" aria-label="Key">
        <li>
          <span className="key key-covered" /> Development ticket, family has a
          playbook
        </li>
        <li>
          <span className="key key-uncovered" /> Unseen family, no playbook
        </li>
        <li>
          <span className="key key-wrong" /> Wrong: a miss or a false match
        </li>
      </ul>
      <div className="chart-layout">
        <ScoreChart
          all={all}
          rule={view.rule}
          chosen={chosen}
          onSelect={setChosen}
        />
        {ticket && <TicketPanel ticket={ticket} rule={view.rule} />}
      </div>
      <TicketTable
        sets={[view.sets.dev, view.sets.unseen_dev]}
        onSelect={setChosen}
      />
    </section>
  );
}

function verdict(result: SearchResult, rule: Rule) {
  const best = result.ranked.at(0);
  if (!best) return "The knowledge base is empty.";
  const next = result.ranked.at(1);
  const ahead = next ? best.score - next.score : best.score;
  if (result.why === "sure") {
    return `It matches ${best.doc}: ${two(best.score)} clears the ${two(rule.sure)} bar on its own.`;
  }
  if (result.why === "clear") {
    return `It matches ${best.doc}: ${two(best.score)} is above ${two(rule.threshold)} and ${two(ahead)} ahead of the next.`;
  }
  if (best.score < rule.threshold) {
    return `No playbook matches: the best, ${best.doc}, scores ${two(best.score)}, under ${two(rule.threshold)}.`;
  }
  return `No playbook matches: ${best.doc} scores ${two(best.score)} but is only ${two(ahead)} ahead of the next, short of ${two(rule.margin)}.`;
}

function TrySearch({ rule }: Readonly<{ rule: Rule }>) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<SearchResult>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = () => {
    setBusy(true);
    setError(undefined);
    api
      .search(text)
      .then(setResult)
      .catch((reason: unknown) => {
        setError(String(reason).replace(/^Error: /, ""));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  return (
    <section className="how-section" aria-labelledby="try">
      <h2 id="try">Try a search</h2>
      <form
        className="try"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label htmlFor="search-text">
          A request, as someone would write it
        </label>
        <textarea
          id="search-text"
          rows={3}
          value={text}
          placeholder="My VPN keeps dropping when I work from home"
          onChange={(event) => {
            setText(event.target.value);
          }}
        />
        <button type="submit" disabled={busy || text.trim() === ""}>
          {busy ? "Searching…" : "Search the knowledge base, free"}
        </button>
      </form>
      {error && (
        <p className="notice alert" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="try-result" aria-live="polite">
          <p className="verdict">{verdict(result, rule)}</p>
          <ScoreBars ranked={result.ranked.slice(0, 5)} rule={rule} />
          {result.given.length > 0 && (
            <>
              <h3>What the agent would be given</h3>
              <ul className="given">
                {result.given.map((unit) => (
                  <li key={`${unit.doc}-${unit.section ?? ""}`}>
                    <code>{unit.doc}</code>{" "}
                    <span className="quiet">
                      {unit.kind}, {two(unit.score)}
                    </span>
                    {unit.highlights[0] && (
                      <q>{plainText(unit.highlights[0].text)}</q>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function Decision({ view }: Readonly<{ view: RetrievalView }>) {
  const { with_search: on, without_search: off } = view.decision;
  const cost = on
    ? `, about ${francs(on.cost_per_ticket_chf * on.n)} on the development set`
    : "";
  const line = (r: NonNullable<typeof on>) =>
    `${percent(r.path_accuracy)}, give or take ${percent(r.path_margin)}, on ${r.n.toString()} tickets`;
  return (
    <section className="how-section" aria-labelledby="decision">
      <h2 id="decision">Does search change the decision?</h2>
      <dl className="answers">
        <dt>Right path with search</dt>
        <dd>{on ? line(on) : "No development run is saved yet."}</dd>
        <dt>Right path without it</dt>
        <dd>
          {off
            ? line(off)
            : `Not measured yet. With search off the agent answers in plain text, with no path to score. Measuring it needs a run where the decision gets no playbook${cost}.`}
        </dd>
      </dl>
      {on && (
        <p className="caption">
          From run <code>{on.run}</code>.
        </p>
      )}
    </section>
  );
}

function Families({ view }: Readonly<{ view: RetrievalView }>) {
  const families = [view.sets.dev, view.sets.unseen_dev].flatMap((set) =>
    Object.entries(set?.by_family ?? {}),
  );
  return (
    <section className="how-section" aria-labelledby="families">
      <h2 id="families">By family</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {[
                "Family",
                "Playbook",
                "Tickets",
                "Hit rate",
                "False matches",
              ].map((name) => (
                <th key={name} scope="col">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {families.map(([code, family]) => (
              <tr key={code}>
                <td>{family.name}</td>
                <td>
                  <code>{family.doc ?? "None"}</code>
                </td>
                <td>{family.n}</td>
                <td>{rate(family.hit_rate)}</td>
                <td>{rate(family.false_match_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SavedScores({ view }: Readonly<{ view: RetrievalView }>) {
  return (
    <section className="how-section" aria-labelledby="saved">
      <h2 id="saved">Every saved score</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {[
                "Date",
                "Set",
                "Knowledge base",
                "Tickets",
                ...MEASURES.map((m) => m.name),
              ].map((name) => (
                <th key={name} scope="col">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...view.history].reverse().map((h) => (
              <tr key={h.id}>
                <td>{dateTime(h.date)}</td>
                <td>
                  {h.set === "dev" ? "development" : "unseen, development"}
                </td>
                <td>
                  <code>{h.kb_version}</code>
                </td>
                <td>{h.summary.n}</td>
                {MEASURES.map((m) => (
                  <td key={m.key}>{rate(h.summary[m.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption">
        Save a new score with <code>uv run -m evals --retrieval --save</code>.
      </p>
    </section>
  );
}

export function Retrieval() {
  const { data: view, error } = useLoad(api.retrieval);
  if (error) {
    return (
      <p className="notice alert" role="alert">
        {error}
      </p>
    );
  }
  if (!view) return <p className="waiting">Loading retrieval scores…</p>;
  if (!view.sets.dev && !view.sets.unseen_dev) {
    return (
      <p className="notice">
        No retrieval score with its tickets is saved yet. Run{" "}
        <code>uv run -m evals --retrieval --save</code> to create one. It calls
        no model, so it's free.
      </p>
    );
  }
  return (
    <div className="how">
      <Lede view={view} />
      <WhyTheBar view={view} />
      <TrySearch rule={view.rule} />
      <Measures view={view} />
      <Decision view={view} />
      <Families view={view} />
      <SavedScores view={view} />
    </div>
  );
}
