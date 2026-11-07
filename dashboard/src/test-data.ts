import type { Evaluations, LabelledTicket, Run, Stats } from "./api";

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
};

export const draft = {
  source: "escalate" as const,
  queue: "SEC-INCIDENT",
  priority: "P2-High",
  summary: "Repeat lockout",
};

export const declined = {
  source: "decline" as const,
  queue: "DESKTOP-SUPPORT",
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

const retrievalSummary = {
  n: 129,
  covered: 90,
  uncovered: 39,
  hit_rate: 0.94,
  false_match_rate: 0.85,
};

const coveredFamily = {
  n: 12,
  covered: 12,
  uncovered: 0,
  hit_rate: 1,
  false_match_rate: null,
};

export const evaluations: Evaluations = {
  costs: { security: 2000, wrong: 120, minor: 60 },
  retrieval: [
    {
      id: "20261107-retrieval-dev",
      date: "2026-11-07T11:41:10+00:00",
      set: "dev",
      kb_version: "5b52d0ab",
      threshold: 0.35,
      top_k: 2,
      summary: retrievalSummary,
      by_family: {
        ALP: {
          ...coveredFamily,
          name: "Account lockout",
          doc: "account-access",
        },
      },
    },
    {
      id: "20261107-retrieval-unseen_dev",
      date: "2026-11-07T11:41:12+00:00",
      set: "unseen_dev",
      kb_version: "5b52d0ab",
      threshold: 0.35,
      top_k: 2,
      summary: { ...retrievalSummary, hit_rate: null, covered: 0 },
      by_family: {
        CES: {
          ...coveredFamily,
          name: "Certificate expiry",
          doc: null,
          hit_rate: null,
          false_match_rate: 0.93,
        },
      },
    },
  ],
  runs: [
    {
      id: "20261104-dev-tiny",
      date: "2026-11-04T22:17:52+00:00",
      set: "dev",
      tiny: true,
      model: "claude-haiku",
      version: "abc12345",
      summary,
      by_difficulty: { hard: summary },
      tickets: [scored],
    },
    {
      id: "20261103-held_out",
      date: "2026-11-03T22:17:52+00:00",
      set: "held_out",
      tiny: false,
      model: "claude-sonnet",
      version: "def67890",
      summary: { ...summary, cost_per_ticket_usd: null },
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
      review: "Maybe too strict.",
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
