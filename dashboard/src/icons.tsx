import type { ViewId } from "./nav";

// One line icon per view, drawn on a 24 px grid in the text's colour.
const PATHS: Record<ViewId | "menu" | "close", string[]> = {
  queue: ["M4 5h4v14H4z", "M10 5h4v9h-4z", "M16 5h4v6h-4z"],
  assistant: ["M5 5h14v10H10l-4 4v-4H5z", "M9 10h6"],
  money: [
    "M12 4a8 8 0 1 0 0 16a8 8 0 0 0 0-16",
    "M14.5 9.5c-.5-1-1.4-1.5-2.5-1.5-1.4 0-2.5.8-2.5 2s1.1 1.6 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1.1 0-2-.5-2.5-1.5",
    "M12 6.5v1.5",
    "M12 16v1.5",
  ],
  models: [
    "M4 20h16",
    "M4 20V4",
    "M8 15h.01",
    "M12 11h.01",
    "M16 8h.01",
    "M15 15h.01",
  ],
  workflow: [
    "M6 4a2 2 0 1 0 0 4a2 2 0 0 0 0-4",
    "M18 16a2 2 0 1 0 0 4a2 2 0 0 0 0-4",
    "M6 8v3a3 3 0 0 0 3 3h6a3 3 0 0 1 3 2",
  ],
  harness: [
    "M7 7h10v10H7z",
    "M10 10h4v4h-4z",
    "M10 3v4",
    "M14 3v4",
    "M10 17v4",
    "M14 17v4",
    "M3 10h4",
    "M3 14h4",
    "M17 10h4",
    "M17 14h4",
  ],
  retrieval: [
    "M10.5 4a6.5 6.5 0 1 0 0 13a6.5 6.5 0 0 0 0-13",
    "M15.5 15.5L20 20",
  ],
  tickets: ["M4 7h16v3a2 2 0 0 0 0 4v3H4v-3a2 2 0 0 0 0-4z", "M10 7v10"],
  evaluations: [
    "M9 6h11",
    "M9 12h11",
    "M9 18h11",
    "M4 6l1 1 2-2",
    "M4 12l1 1 2-2",
    "M4 18l1 1 2-2",
  ],
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  close: ["M6 6l12 12", "M18 6L6 18"],
};

/** A line icon. It is decoration, so a screen reader skips it. */
export function Icon({ name }: Readonly<{ name: keyof typeof PATHS }>) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
