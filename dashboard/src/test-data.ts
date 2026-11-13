import type {
  Evaluations,
  LabelledTicket,
  QueueDecision,
  QueueTicket,
  QueueView,
  Run,
  Stats,
  Trace,
  TriageExample,
} from "./api";
import type { Person } from "./people";

export const unit = {
  doc: "vpn",
  section: null,
  text: "VPN **playbook**",
  score: 0.81,
  highlights: [{ text: "Reset the **profile**", score: 0.72 }],
};

export const baseRun: Run = {
  id: "run1",
  query: "My VPN fails",
  use_retrieval: true,
  retrieved: [unit],
  path: "AUTO_FIX",
  reasoning: "Reset the profile.",
  tool_name: "reset_vpn_profile",
  tool_input: { username: "a.b" },
  human_decision: {},
  ticket_draft: null,
  tool_result: null,
  pending: {
    kind: "confirm_fix",
    tool_name: "reset_vpn_profile",
    tool_input: { username: "a.b" },
  },
  rule: null,
  design: "loop",
  steps: [
    {
      id: "s1",
      turn: 1,
      tool: "lookup_requester",
      input: {},
      result: "Finance, Zürich; 2 lockouts in 24 hours; device LT-SKELLER.",
      ok: true,
      time_sec: 1.1,
      cost_chf: 0.0009,
    },
    {
      id: "s2",
      turn: 2,
      tool: "record_decision",
      input: { path: "AUTO_FIX" },
      result: "AUTO_FIX",
      ok: true,
      time_sec: 1.2,
      cost_chf: 0.0011,
    },
  ],
  stopped: null,
  requester: { id: "s.keller", department: "Finance", office: "Zürich" },
  status: "waiting",
  error: null,
  next: ["confirm_fix"],
  cause: "Stale VPN profile",
  handover: null,
  citations: null,
  response_time_sec: 2.3,
  cost_chf: 0.002,
};

export const examples: TriageExample[] = [
  {
    id: "INC-ALP-0010",
    title: "account locked after password change",
    text: "account locked after password change\n\nI changed my password.",
    requester: "m.huber",
  },
];

export const requesters: Person[] = [
  {
    id: "s.keller",
    name: "Sara Keller",
    department: "Finance",
    office: "Zürich",
    lockouts_24h: 2,
    device: {
      id: "LT-SKELLER",
      model: "ThinkPad T14",
      image: "2026-06",
      age_years: 2,
      battery_health: 90,
    },
    rules_set: true,
  },
  {
    id: "m.huber",
    name: "Marc Huber",
    department: "Sales",
    office: "Munich",
    lockouts_24h: 1,
    device: {
      id: "LT-MHUBER",
      model: "HP EliteBook 840",
      image: "2026-04",
      age_years: 2,
      battery_health: 90,
    },
    rules_set: true,
  },
  {
    id: "a.hussain",
    name: "Amir Hussain",
    department: "Finance",
    office: "Charlotte",
    lockouts_24h: 0,
    device: {
      id: "LT-AHUSSAIN",
      model: "HP EliteBook 840",
      image: "2026-06",
      age_years: 2,
      battery_health: 90,
    },
    rules_set: false,
  },
];

export const draft = {
  source: "escalate" as const,
  queue: "SEC-INCIDENT",
  priority: "P2-High",
  summary: "Repeat lockout",
};

export const declined = {
  source: "decline" as const,
  queue: "DESK-SUPPORT",
  priority: "P3-Normal",
  summary: "Declined",
  declined_tool: "reset_vpn_profile",
  reason: "User declined",
  diagnostic_summary: "Profile is stale",
};

export const result = {
  detail: "Ran the script.",
  timestamp: "2026-11-06T10:00:00+00:00",
};

const summary = {
  n: 5,
  path_accuracy: 0.8,
  action_accuracy: 0.6,
  retrieval_accuracy: 1,
  automation_rate: 0.5,
  mistake_cost_chf: 2120,
  cost_per_ticket_usd: 0.0047,
  time_per_ticket_sec: 1.5,
  path_margin: 0.1,
  action_margin: 0.1,
  team_accuracy: 0.75,
  team_margin: 0.2,
  cause_accuracy: null,
  cost_per_ticket_chf: 0.0032,
  kappa: 0.71,
};

const yardstick = {
  n: 25,
  path_accuracy: 0.5,
  path_margin: 0.2,
  action_accuracy: 0.4,
  action_margin: 0.2,
  team_accuracy: null,
  team_margin: null,
  mistake_cost_chf: 900,
  kappa: null,
};

const paths = ["SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"];

const pathDetail = {
  yardsticks: { most_common: yardstick, classifier: yardstick },
  confusion: Object.fromEntries(
    paths.map((path) => [path, Object.fromEntries(paths.map((p) => [p, 1]))]),
  ),
  per_path: Object.fromEntries(
    paths.map((path) => [path, { precision: 0.5, recall: null, n: 4 }]),
  ),
  by_family: { "VPN access": summary },
  kb_version: "916db54c",
};

const scored = {
  id: "T-001",
  text: "My VPN keeps disconnecting",
  difficulty: "hard",
  expected_paths: ["AUTO_FIX"],
  expected_tools: ["reset_vpn_profile"],
  expected_queues: [],
  path: "ESCALATE",
  tool: "create_escalation_ticket",
  queue: "NETWORK",
  action_correct: false,
  mistake_cost_chf: 120,
  error: null,
};

export const evaluations: Evaluations = {
  costs: { security: 2000, wrong: 120, minor: 60 },
  runs: [
    {
      id: "20261104-dev-tiny",
      date: "2026-11-04T22:17:52+00:00",
      set: "rules",
      tiny: true,
      model: "claude-haiku",
      version: "abc12345",
      summary,
      ...pathDetail,
      by_difficulty: { hard: summary },
      tickets: [scored],
    },
    {
      id: "20261103-held_out",
      date: "2026-11-03T22:17:52+00:00",
      set: "rules_held_out",
      tiny: false,
      sample: true,
      rescored_from: "20261102-held_out",
      model: "claude-sonnet",
      version: "def67890",
      summary: {
        ...summary,
        cost_per_ticket_usd: null,
        cost_per_ticket_chf: null,
      },
      ...pathDetail,
      by_difficulty: {},
      tickets: [],
    },
  ],
};

const requester = {
  id: "s.keller",
  name: "Sandra Keller",
  department: "Client Services",
  floor: 4,
  lockouts_24h: 2,
  device: {
    id: "LT-SKELLER",
    model: "ThinkPad T14",
    image: "2026-06",
    age_years: 1,
    battery_health: 92,
  },
  groups: [],
  recent_tickets: ["Account lockout"],
};

export const tickets: LabelledTicket[] = [
  {
    id: "T-001",
    text: "My VPN keeps disconnecting",
    answer: {
      paths: ["AUTO_FIX"],
      tools: ["reset_vpn_profile"],
      queues: [],
      units: ["vpn"],
      difficulty: "hard",
      note: "A note",
      family: "Rules set",
      cause: null,
      checks: [],
    },
    requester,
    latest: scored,
  },
  {
    id: "T-002",
    text: "I'm locked out",
    answer: {
      paths: ["ESCALATE"],
      tools: [],
      queues: ["SEC-INCIDENT"],
      units: [],
      difficulty: "records",
      note: "",
      family: "Account lockout",
      cause: "Stale phone credentials",
      checks: ["account-lockout-source-check"],
      root_cause: "A phone kept sending the old password.",
    },
    requester: { ...requester, lockouts_24h: 0 },
    latest: null,
  },
];

export const stats: Stats = {
  n: 3,
  paths: ["SELF_SERVE", "AUTO_FIX"],
  counts: { SELF_SERVE: 1, AUTO_FIX: 2 },
  pct: { SELF_SERVE: 33.3, AUTO_FIX: 66.6 },
  automation_rate: 100,
  avg_response_time_sec: { SELF_SERVE: null, AUTO_FIX: 1.5 },
  low_sample: true,
};

const fixDecision: QueueDecision = {
  path: "AUTO_FIX",
  cause: "Stale VPN profile",
  reasoning: "The profile predates the **migration**.",
  tool: "reset_vpn_profile",
  tool_input: { username: "a.b" },
  queue: null,
  priority: null,
  summary: null,
  retrieved: [{ doc: "vpn-access", section: "Fix", score: 0.61 }],
};

export const queueTicket: QueueTicket = {
  id: "INC-VPN-0001",
  batch: "20261108T090000",
  title: "VPN drops every few minutes",
  description: "Since the migration my VPN disconnects.",
  priority: "high",
  sla_plan: "Business-hours SLA",
  submitted_at: "2026-11-08T08:00:00Z",
  applications: ["GlobalProtect"],
  requester: {
    id: "a.b",
    name: "Anna Berg",
    department: "Finance",
    office: "Zurich",
    device: "LT-ABERG",
  },
  state: "review",
  decision: fixDecision,
  agent_seconds: 3.2,
  cost_chf: 0.0036,
  trace_id: "t1",
  trace_url: "https://cloud.langfuse.com/project/p/traces/t1",
  review: null,
  error: null,
};

export const escalationTicket: QueueTicket = {
  ...queueTicket,
  id: "INC-SEC-0002",
  title: "Locked out again",
  decision: {
    ...fixDecision,
    path: "ESCALATE",
    tool: null,
    tool_input: null,
    queue: "SEC-INCIDENT",
    priority: "P2-High",
    summary: "Repeat lockout, a possible compromise.",
  },
};

export const queuedTicket: QueueTicket = {
  ...queueTicket,
  id: "INC-PRT-0003",
  title: "Printer on floor 3 is jammed",
  state: "queued",
  decision: null,
  agent_seconds: null,
  cost_chf: null,
  trace_id: null,
  trace_url: null,
};

export const failedTicket: QueueTicket = {
  ...queuedTicket,
  id: "INC-WIF-0004",
  title: "Wi-Fi keeps dropping",
  state: "failed",
  error: "RuntimeError: model unavailable",
};

export const closedTicket: QueueTicket = {
  ...queueTicket,
  id: "INC-VPN-0005",
  title: "VPN certificate expired",
  state: "closed",
  review: {
    verdict: "corrected",
    seconds: 75,
    queue: "NET-VPN",
    note: "",
    outcome: {
      detail: "Ticket #INC1234567 opened in NET-VPN (priority: P3-Normal).",
    },
    at: "2026-11-08T09:10:00Z",
  },
};

const value = {
  model_cost_chf: 0,
  agent_seconds: null,
  reviewed: 0,
  approved: 0,
  review_seconds: null,
};

const noTickets = { queued: 0, working: 0, review: 0, closed: 0, failed: 0 };

export const emptyQueue: QueueView = {
  tickets: [],
  counts: noTickets,
  at_desk: 129,
  batch_size: 8,
  queues: ["NET-VPN", "SEC-INCIDENT"],
  value,
};

export const busyQueue: QueueView = {
  ...emptyQueue,
  tickets: [
    queueTicket,
    escalationTicket,
    queuedTicket,
    failedTicket,
    closedTicket,
  ],
  counts: { queued: 1, working: 0, review: 2, closed: 1, failed: 1 },
  at_desk: 121,
  value: {
    ...value,
    model_cost_chf: 0.0144,
    agent_seconds: 3.2,
    reviewed: 1,
    approved: 0,
    review_seconds: 75,
  },
};

export const readyTrace: Trace = {
  status: "ready",
  url: "https://cloud.langfuse.com/project/p/traces/t1",
  steps: [
    {
      name: "retrieve",
      type: "CHAIN",
      start_ms: 0,
      duration_ms: 400,
      model: null,
      input_tokens: null,
      output_tokens: null,
      cost_usd: null,
    },
    {
      name: "ChatAnthropic",
      type: "GENERATION",
      start_ms: 400,
      duration_ms: 2500,
      model: "claude-haiku-4-5-20251001",
      input_tokens: 3564,
      output_tokens: 189,
      cost_usd: 0.0045,
    },
  ],
};
