export const pathLabels: Record<string, string> = {
  SELF_SERVE: "Self-serve",
  AUTO_FIX: "Auto-fix",
  ESCALATE: "Escalate",
  OUT_OF_SCOPE: "Out of scope",
  NO_TOOLS: "No tools, retrieval off",
};

export const percent = (share: number) => `${(share * 100).toFixed(0)}%`;

export const rate = (share?: number | null) =>
  share === null || share === undefined ? "n/a" : percent(share);

export const money = (usd: number | null) =>
  usd === null ? "unknown" : `$${usd.toFixed(4)}`;

export const rappen = (amount: number | null) =>
  amount === null ? "unknown" : `CHF ${amount.toFixed(4)}`;

export const francs = (amount: number) =>
  `CHF ${amount.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const minutes = (amount: number) => `${amount.toFixed(1)} min`;

/** A duration in seconds, as "8 s" or "1:05". */
export const seconds = (amount: number | null) => {
  if (amount === null) return "n/a";
  if (amount < 60) return `${amount.toFixed(amount < 10 ? 1 : 0)} s`;
  const whole = Math.round(amount);
  const rest = (whole % 60).toString().padStart(2, "0");
  return `${Math.floor(whole / 60).toString()}:${rest}`;
};

export const chf = (amount: number) => amount.toLocaleString("de-CH");

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });

/** Knowledge base highlights are plain text, so drop their markdown. */
export const plainText = (text: string) => text.replaceAll(/\*\*|`|\*/g, "");
