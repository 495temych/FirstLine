import type { Path, Requester } from "./api";

/** Someone in the staff directory a ticket can come from, for the picker. */
export type Person = Pick<
  Requester,
  "id" | "name" | "department" | "lockouts_24h" | "device"
> & { office: string; rules_set: boolean };

/** A rule in agent/rules.py that changed the agent's decision. */
export interface RuleOverride {
  rule: string;
  reason: string;
  code: string;
  proposed: {
    path: Path;
    tool_name: string | null;
    tool_input: Record<string, unknown> | null;
  };
}
