import type { Harness, HarnessTicket } from "./harnessData";

/** What `GET /api/harness` returns, for the tests. */
export const harness: Harness = {
  answer:
    "For each ticket, code searches the knowledge base, then the model answers once.",
  instructions: {
    file: "agent/prompt.md",
    words: 802,
    sections: ["Step 0 — Scope check", "Hard rules"],
    text: "**Step 0 — Scope check**\nIs it IT?",
  },
  search: {
    embedding_model: "all-MiniLM-L6-v2",
    sure: 0.52,
    threshold: 0.4,
    margin: 0.15,
    support: 0.35,
    top_k: 2,
  },
  reads: [
    {
      name: "Instructions",
      role: "system",
      what: "How to triage.",
      code: "agent/prompt.md",
    },
    {
      name: "The fixes it may propose",
      role: "system",
      what: "Each fix.",
      code: "tool_guide in agent/decision.py",
    },
    {
      name: "The ticket",
      role: "user",
      what: "As written.",
      code: "build_user_message in agent/graph.py",
    },
    {
      name: "What search found",
      role: "user",
      what: "The best playbook.",
      code: "retrieve in agent/retrieval.py",
    },
  ],
  fixes: 16,
  model: {
    name: "qwen/qwen3.7-flash",
    label: "Qwen 3.7 Flash",
    lab: "openrouter",
    provider: "alibaba",
    region: "unconfirmed",
    effort: "none",
    max_tokens: 2048,
    attempts: 3,
    forced: false,
  },
  tool: {
    name: "record_decision",
    description: "Record your triage decision.",
    fields: [
      {
        name: "rationale",
        means: "Its reasoning.",
        required: true,
        choices: null,
      },
      {
        name: "path",
        means: "The path.",
        required: true,
        choices: ["SELF_SERVE", "AUTO_FIX", "ESCALATE", "OUT_OF_SCOPE"],
      },
      {
        name: "queue",
        means: "The team.",
        required: false,
        choices: ["NET-VPN", "DESK-SUPPORT"],
      },
    ],
  },
  checks: [
    {
      when: "The answer doesn't fit the form",
      then: "It becomes an escalation to DESK-SUPPORT.",
      code: "read_decision in agent/decision.py",
    },
  ],
  loop: { built: false, calls: 1, text: "There's no loop yet." },
  gates: ["Approve the fix", "Approve the ticket"],
  examples: [
    { id: "INC-VDA-0001", title: "VPN drops", family: "VPN access" },
    { id: "INC-DNS-0002", title: "Name fails", family: "DNS" },
  ],
};

export const vpnTicket: HarnessTicket = {
  id: "INC-VDA-0001",
  run: "20261109T145222-dev",
  found: [{ doc: "vpn-access", kind: "playbook", section: null, score: 0.61 }],
  message: "User issue: VPN drops",
  answer: {
    path: "ESCALATE",
    cause: "Expired device certificate",
    tool: null,
    queue: "NET-VPN",
    invalid: false,
    right: false,
    expected: ["AUTO_FIX"],
  },
};

export const dnsTicket: HarnessTicket = {
  ...vpnTicket,
  id: "INC-DNS-0002",
  found: [],
  message: "User issue: Name fails",
  answer: { ...vpnTicket.answer, invalid: true },
};
