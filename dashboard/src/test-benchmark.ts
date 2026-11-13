import type { Benchmark, BenchmarkEntry, LoopView } from "./benchmark";

const model = (
  name: string,
  label: string,
  fields: Partial<BenchmarkEntry> = {},
): BenchmarkEntry => ({
  model: name,
  label,
  kind: "model",
  source: `20261109-dev-${name}`,
  sample: false,
  serving: { lab: "openai", provider: "openai", region: "US", effort: "none" },
  n: 129,
  net_chf: 2,
  net_low: 1,
  net_high: 3,
  cost_chf: 0.001,
  time_p50_sec: 3,
  time_p90_sec: 6,
  path_accuracy: 0.8,
  path_margin: 0.07,
  action_accuracy: 0.75,
  balanced_accuracy: 0.6,
  mistake_cost_chf: 2400,
  security_mistakes: 0,
  invalid: 0,
  front_cost: true,
  front_time: true,
  ...fields,
});

const classifier: BenchmarkEntry = {
  ...model("classifier", "Classifier"),
  kind: "yardstick",
  serving: null,
  net_chf: 10.72,
  cost_chf: 0,
  time_p50_sec: null,
  time_p90_sec: null,
  balanced_accuracy: null,
  security_mistakes: null,
  front_cost: false,
  front_time: false,
};

const dev = [
  model("dear", "Dear model", {
    net_chf: 2.5,
    cost_chf: 0.005,
    time_p50_sec: 5,
    serving: {
      lab: "openrouter",
      provider: "mistral/eu",
      region: "EU",
      effort: null,
    },
  }),
  model("cheap", "Cheap model"),
  model("beaten", "Beaten model", {
    net_chf: -1,
    net_low: -2,
    net_high: 0,
    cost_chf: 0.004,
    time_p50_sec: 9,
    front_cost: false,
    front_time: false,
    security_mistakes: 1,
    sample: true,
    serving: {
      lab: "openrouter",
      provider: "alibaba",
      region: "unconfirmed",
      effort: null,
    },
  }),
  classifier,
];

export const benchmark: Benchmark = {
  sets: {
    dev: { set: "dev", entries: dev },
    unseen_dev: { set: "unseen_dev", entries: [] },
    rules: { set: "rules", entries: [model("cheap", "Cheap model")] },
  },
  rule: "The cheapest model on the cost front whose net saving is within the margin of the best.",
  chosen: { model: "cheap", label: "Cheap model", best: "dear" },
  default: { model: "dear", label: "Dear model" },
  insights: [
    {
      question: "Which model saves the most?",
      answer: "Dear model, CHF 2.50 a ticket.",
    },
  ],
  catch_rate: 0.9,
  loop: {
    rule: "Keep the loop for a model if it clearly saves more.",
    sets: { dev: [], unseen_dev: [], rules: [] },
    verdicts: {},
  },
};

/** Gemini's loop beside its one call on the same 36 development tickets. */
export const loopView: LoopView = {
  rule: "Keep the loop for a model if it clearly saves more.",
  sets: {
    dev: [
      {
        model: "gemini",
        label: "Gemini",
        n: 36,
        one_call: model("gemini", "Gemini", {
          n: 36,
          net_chf: 4,
          cost_chf: 0.001,
        }),
        loop: model("gemini", "Gemini", {
          n: 36,
          design: "loop",
          source: "20261113-dev-loop-sample",
          net_chf: 6,
          net_low: 5,
          net_high: 7,
          cost_chf: 0.005,
          action_accuracy: 0.9,
          investigation: {
            tickets: 36,
            lookups_per_ticket: 2.5,
            required_checks: 40,
            required_run: 30,
            required_share: 0.75,
            needless_per_ticket: 0.4,
            citations: 50,
            citations_valid: 0.96,
            citations_dropped: 2,
          },
        }),
      },
    ],
    unseen_dev: [],
    rules: [],
  },
  verdicts: {
    gemini: {
      saves_more: true,
      safe: true,
      valid: true,
      cheap: true,
      keep: true,
      gain_chf: 2,
      extra_cost_chf: 0.004,
    },
  },
};
