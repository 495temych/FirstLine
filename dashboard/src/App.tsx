import { useState } from "react";
import { Scoreboard } from "./Scoreboard";
import { Tickets } from "./Tickets";
import { Triage } from "./Triage";

const tabs = ["Triage", "Scoreboard", "Tickets"] as const;
type Tab = (typeof tabs)[number];

export function App() {
  const [tab, setTab] = useState<Tab>("Triage");

  return (
    <>
      <header className="masthead">
        <div>
          <h1>TriagePilot</h1>
          <p>L1 IT support for Limmatica AG</p>
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
        <div hidden={tab !== "Triage"}>
          <Triage />
        </div>
        {tab === "Scoreboard" && <Scoreboard />}
        {tab === "Tickets" && <Tickets />}
      </main>
    </>
  );
}
