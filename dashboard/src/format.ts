export const pathLabels: Record<string, string> = {
  SELF_SERVE: "Self-serve",
  AUTO_FIX: "Auto-fix",
  ESCALATE: "Escalate",
  OUT_OF_SCOPE: "Out of scope",
  NO_TOOLS: "No tools, retrieval off",
};

export const percent = (share: number) => `${(share * 100).toFixed(0)}%`;

export const rate = (share: number | null) =>
  share === null ? "n/a" : percent(share);

export const money = (usd: number | null) =>
  usd === null ? "unknown" : `$${usd.toFixed(4)}`;

export const chf = (amount: number) => amount.toLocaleString("de-CH");

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });

/** Knowledge base highlights are plain text, so drop their markdown. */
export const plainText = (text: string) => text.replaceAll(/\*\*|`|\*/g, "");
