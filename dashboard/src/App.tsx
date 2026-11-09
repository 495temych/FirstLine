import { useState } from "react";
import { Scoreboard } from "./Scoreboard";
import { Tickets } from "./Tickets";
import { Assistant } from "./Assistant";
import { Queue } from "./Queue";
import { HowItWorks } from "./HowItWorks";
import { Retrieval } from "./Retrieval";

const tabs = [
  "Queue",
  "Assistant",
  "Scoreboard",
  "Retrieval",
  "Tickets",
  "How it works",
] as const;
type Tab = (typeof tabs)[number];

export function App() {
  // A link to a paused Assistant run opens the Assistant. Everything else opens
  // the Queue, the core of the product.
  const [tab, setTab] = useState<Tab>(() =>
    new URLSearchParams(window.location.search).has("run")
      ? "Assistant"
      : "Queue",
  );

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
        {/* Both stay mounted, so a running batch or a paused run survives a tab switch. */}
        <div hidden={tab !== "Queue"}>
          <Queue />
        </div>
        <div hidden={tab !== "Assistant"}>
          <Assistant />
        </div>
        {tab === "Scoreboard" && <Scoreboard />}
        {tab === "Tickets" && <Tickets />}
        {tab === "Retrieval" && <Retrieval />}
        {tab === "How it works" && <HowItWorks />}
      </main>
    </>
  );
}
