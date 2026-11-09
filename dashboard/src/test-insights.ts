import type { Insights } from "./insights";

/** What `GET /api/insights` returns, for the tests. */
export const insights: Insights = {
  try: {
    question: "What does it do?",
    findings: [
      {
        text: "The model proposes and a person decides: nothing runs until one of 3 human gates says yes.",
        n: null,
        source: "agent/graph.py",
        view: "queue",
      },
    ],
  },
  worth: {
    question: "Does it pay, and on which model?",
    findings: [
      {
        text: "On Claude Haiku 4.5, the default, each ticket saves CHF 0.97 net if technicians catch 90% of wrong decisions.",
        n: 129,
        source: "20261109T145222-dev-rescored",
        view: "money",
      },
    ],
  },
  how: {
    question: "Why does it decide that, and how do we know?",
    findings: [
      {
        text: "Search finds the right playbook for 100% of 129 development tickets.",
        n: 129,
        source: "20261109T105136-retrieval-dev",
        view: "retrieval",
      },
    ],
  },
};
