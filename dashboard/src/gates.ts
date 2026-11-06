import type { Run } from "./api";

export type ActionState =
  | "out_of_scope"
  | "no_tools"
  | "await_self_serve"
  | "await_fix"
  | "await_ticket"
  | "await_declined_ticket"
  | "resolved"
  | "fix_done"
  | "ticket_done"
  | "skipped";

/** What the Action step shows, from the run's path, gate and answers. */
export function actionState(run: Run): ActionState {
  const { path, pending, human_decision: decision } = run;
  if (path === "OUT_OF_SCOPE") return "out_of_scope";
  if (path === "NO_TOOLS") return "no_tools";
  if (pending?.kind === "self_serve") return "await_self_serve";
  if (pending?.kind === "confirm_fix") return "await_fix";
  if (pending) {
    return path === "AUTO_FIX" ? "await_declined_ticket" : "await_ticket";
  }
  if (decision.resolved) return "resolved";
  if (decision.fix) return "fix_done";
  if (decision.ticket) return "ticket_done";
  return "skipped";
}
