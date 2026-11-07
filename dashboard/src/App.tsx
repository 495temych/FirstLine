import { useState } from "react";
import { Scoreboard } from "./Scoreboard";
import { Tickets } from "./Tickets";
import { Assistant } from "./Assistant";

const tabs = ["Assistant", "Scoreboard", "Tickets"] as const;
type Tab = (typeof tabs)[number];

export function App() {
  const [tab, setTab] = useState<Tab>("Assistant");

  return (
    <>
      <header className="masthead">
        <div>
          <h1>FirstLine</h1>
          <p>L1 IT support for CorpLabs AG</p>
        </div>
        <nav aria-label="Sections">
          {tabs.map((name) => (
            <button
              key={name}
              type="button"
              aria-current={tab === name ? "page" : undefined}
              onClick={() => {
                setTab(name);
              }}
            >
              {name}
            </button>
          ))}
        </nav>
      </header>
      <main>
        <div hidden={tab !== "Assistant"}>
          <Assistant />
        </div>
        {tab === "Scoreboard" && <Scoreboard />}
        {tab === "Tickets" && <Tickets />}
      </main>
    </>
  );
}
