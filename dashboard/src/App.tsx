import { useEffect, useState, type MouseEvent, type ReactNode } from "react";
import { api } from "./api";
import { Assistant } from "./Assistant";
import { BusinessCase } from "./BusinessCase";
import { Evaluations } from "./Evaluations";
import { Harness } from "./Harness";
import { HowItWorks } from "./HowItWorks";
import { Models } from "./Models";
import { Icon } from "./icons";
import {
  groupOf,
  groups,
  labelOf,
  linkTo,
  questionOf,
  viewFrom,
  type ViewId,
} from "./nav";
import { Queue } from "./Queue";
import { Retrieval } from "./Retrieval";
import { Tickets } from "./Tickets";
import { useLoad } from "./useLoad";

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
  children: ReactNode;
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

/** The sidebar: every group and its views, and the model the agent runs on. */
function Sidebar(
  props: Readonly<{ view: ViewId; go: (view: ViewId) => void }>,
) {
  const { data: health } = useLoad(api.health);
  return (
    <>
      <p className="brand">
        <span className="brand-mark" aria-hidden="true">
          FL
        </span>
        <span>
          FirstLine
          <span className="brand-sub">CorpLabs AG service desk</span>
        </span>
      </p>
      <nav className="side-nav" aria-label="Views">
        {groups.map((g) => (
          <div key={g.id} className="nav-group">
            <p className="nav-group-name" id={`group-${g.id}`}>
              {g.label}
            </p>
            <ul aria-labelledby={`group-${g.id}`}>
              {g.views.map((v) => (
                <li key={v.id}>
                  <ViewLink
                    view={v.id}
                    current={v.id === props.view}
                    go={props.go}
                  >
                    <Icon name={v.id} />
                    {v.label}
                  </ViewLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      {health?.model && (
        <p className="side-foot">
          Runs on <strong>{health.model}</strong>
        </p>
      )}
    </>
  );
}

export function App() {
  const [view, setView] = useState<ViewId>(() =>
    viewFrom(window.location.search),
  );
  const [menu, setMenu] = useState(false);
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
    setMenu(false);
  };

  return (
    <div className="app">
      <aside className="sidebar" data-open={menu} id="sidebar">
        <Sidebar view={view} go={go} />
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            type="button"
            className="menu-button"
            aria-expanded={menu}
            aria-controls="sidebar"
            onClick={() => {
              setMenu(!menu);
            }}
          >
            <Icon name={menu ? "close" : "menu"} />
            <span className="sr-only">Menu</span>
          </button>
          <p className="crumbs">
            <span>{group.label}</span>
            <span aria-hidden="true">/</span>
            <span aria-current="location">{labelOf(view)}</span>
          </p>
        </header>
        <main>
          <header className="page-head">
            <h1>{labelOf(view)}</h1>
            <p>{questionOf(view)}</p>
          </header>
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
      </div>
    </div>
  );
}
