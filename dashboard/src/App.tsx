import { useEffect, useState, type MouseEvent } from "react";
import { Assistant } from "./Assistant";
import { BusinessCase } from "./BusinessCase";
import { Evaluations } from "./Evaluations";
import { Harness } from "./Harness";
import { HowItWorks } from "./HowItWorks";
import { Models } from "./Models";
import { groupOf, groups, linkTo, viewFrom, type ViewId } from "./nav";
import { Queue } from "./Queue";
import { Retrieval } from "./Retrieval";
import { Tickets } from "./Tickets";

/** A link to a view that opens without reloading the page. */
function ViewLink({
  view,
  current,
  go,
  children,
}: Readonly<{
  view: ViewId;
  current: boolean;
  go: (view: ViewId) => void;
  children: string;
}>) {
  return (
    <a
      href={linkTo(view, window.location.search)}
      aria-current={current ? "page" : undefined}
      onClick={(event: MouseEvent) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey) return;
        event.preventDefault();
        go(view);
      }}
    >
      {children}
    </a>
  );
}

export function App() {
  const [view, setView] = useState<ViewId>(() =>
    viewFrom(window.location.search),
  );
  const group = groupOf(view);

  useEffect(() => {
    const back = () => {
      setView(viewFrom(window.location.search));
    };
    window.addEventListener("popstate", back);
    return () => {
      window.removeEventListener("popstate", back);
    };
  }, []);

  const go = (next: ViewId) => {
    window.history.pushState(null, "", linkTo(next, window.location.search));
    setView(next);
  };

  return (
    <>
      <header className="masthead">
        <div>
          <h1>FirstLine</h1>
          <p>L1 IT support for CorpLabs AG</p>
        </div>
        <nav aria-label="Groups">
          {groups.map((g) => (
            <ViewLink
              key={g.id}
              view={g.views[0].id}
              current={g.id === group.id}
              go={go}
            >
              {g.label}
            </ViewLink>
          ))}
        </nav>
      </header>
      <nav className="views" aria-label={group.label}>
        {group.views.map((v) => (
          <ViewLink key={v.id} view={v.id} current={v.id === view} go={go}>
            {v.label}
          </ViewLink>
        ))}
      </nav>
      <main>
        {/* Both stay mounted, so a running batch or a paused run survives a switch. */}
        <div hidden={view !== "queue"}>
          <Queue />
        </div>
        <div hidden={view !== "assistant"}>
          <Assistant />
        </div>
        {view === "money" && <BusinessCase />}
        {view === "models" && <Models />}
        {view === "workflow" && <HowItWorks />}
        {view === "harness" && <Harness />}
        {view === "retrieval" && <Retrieval />}
        {view === "tickets" && <Tickets />}
        {view === "evaluations" && <Evaluations />}
      </main>
    </>
  );
}
