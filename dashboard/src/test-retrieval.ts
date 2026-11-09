import type { RetrievalTicket, RetrievalView, SearchResult } from "./api";

const ticket = (over: Partial<RetrievalTicket>): RetrievalTicket => ({
  id: "INC-VDA-0001",
  title: "VPN drops at home",
  family: "VDA",
  expected: "vpn-access",
  top: "vpn-access",
  score: 0.7,
  hit: true,
  false_match: false,
  rank: 1,
  right_score: 0.7,
  best_wrong_score: 0.4,
  ranked: [
    { doc: "vpn-access", section: "Symptoms", score: 0.7 },
    { doc: "wifi", section: null, score: 0.4 },
  ],
  also: [{ doc: "sec-04", kind: "policy", section: null, score: 0.38 }],
  ...over,
});

const summary = {
  n: 2,
  covered: 2,
  uncovered: 0,
  hit_rate: 0.5,
  mean_reciprocal_rank: 0.75,
  recall: 1,
  false_match_rate: null,
};

const run = {
  date: "2026-11-09T10:51:36+00:00",
  kb_version: "916db54c",
  threshold: 0.4,
  top_k: 2,
};

export const retrievalView: RetrievalView = {
  sets: {
    dev: {
      ...run,
      id: "20261109-retrieval-dev",
      set: "dev",
      summary,
      by_family: {
        VDA: { ...summary, name: "VPN access", doc: "vpn-access" },
      },
      tickets: [
        ticket({}),
        ticket({
          id: "INC-VDA-0002",
          title: "Tunnel will not connect",
          top: "wifi",
          hit: false,
          rank: 2,
          right_score: 0.45,
          best_wrong_score: 0.55,
          also: [],
        }),
      ],
    },
    unseen_dev: {
      ...run,
      id: "20261109-retrieval-unseen_dev",
      set: "unseen_dev",
      summary: {
        ...summary,
        covered: 0,
        uncovered: 2,
        hit_rate: null,
        mean_reciprocal_rank: null,
        recall: null,
        false_match_rate: 0.5,
      },
      by_family: {
        CES: {
          ...summary,
          name: "Certificate expiry",
          doc: null,
          hit_rate: null,
          false_match_rate: 0.5,
        },
      },
      tickets: [
        ticket({
          id: "INC-CES-0002",
          title: "Expired TLS certificate",
          family: "CES",
          expected: null,
          top: "vpn-access",
          false_match: true,
          rank: null,
          right_score: null,
          ranked: [
            { doc: "vpn-access", section: "Known causes", score: 0.53 },
            { doc: "wifi", section: "Symptoms", score: 0.48 },
          ],
        }),
        ticket({
          id: "INC-CES-0003",
          title: "Certificate warning",
          family: "CES",
          expected: null,
          top: null,
          score: null,
          hit: false,
          rank: null,
          right_score: null,
          ranked: [{ doc: "wifi", section: null, score: 0.3 }],
        }),
      ],
    },
  },
  history: [
    {
      id: "a",
      date: "2026-11-07T11:41:10+00:00",
      set: "dev",
      kb_version: "5b52d0ab",
      summary: { ...summary, hit_rate: 0.94, mean_reciprocal_rank: undefined },
    },
    {
      id: "b",
      date: "2026-11-09T10:51:36+00:00",
      set: "dev",
      kb_version: "916db54c",
      summary,
    },
    {
      id: "c",
      date: "2026-11-09T10:51:44+00:00",
      set: "unseen_dev",
      kb_version: "916db54c",
      summary: { ...summary, false_match_rate: 0.5 },
    },
  ],
  questions: {
    hit_rate: "When a family has a playbook, is it the one found?",
    mean_reciprocal_rank: "How high does the right playbook rank?",
    recall: "Is the right playbook in the first 2?",
    false_match_rate: "When a family has no playbook, does search stay quiet?",
  },
  floors: { hit_rate: 0.95 },
  rule: { sure: 0.52, threshold: 0.4, margin: 0.15, support: 0.35, top_k: 2 },
  embedding_model: "all-MiniLM-L6-v2",
  kb_version: "916db54c",
  decision: {
    with_search: {
      run: "20261108T010442-dev-rescored",
      n: 129,
      path_accuracy: 0.73,
      path_margin: 0.08,
      cost_per_ticket_chf: 0.005,
    },
    without_search: null,
  },
};

const ranked = (scores: number[]) =>
  scores.map((score, i) => ({
    doc: `doc-${i.toString()}`,
    section: null,
    score,
  }));

export const searches: Record<string, SearchResult> = {
  sure: {
    ranked: ranked([0.6, 0.3]),
    why: "sure",
    given: [
      {
        doc: "doc-0",
        kind: "playbook",
        section: null,
        score: 0.6,
        highlights: [{ text: "Reset the **VPN** profile.", score: 0.5 }],
      },
    ],
  },
  clear: { ranked: ranked([0.45, 0.25]), why: "clear", given: [] },
  low: { ranked: ranked([0.3, 0.2]), why: null, given: [] },
  close: { ranked: ranked([0.45, 0.4]), why: null, given: [] },
  empty: { ranked: [], why: null, given: [] },
};
