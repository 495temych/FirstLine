import type { Benchmark, BenchmarkEntry } from "./benchmark";

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
  insights: [
    {
      question: "Which model saves the most?",
      answer: "Dear model, CHF 2.50 a ticket.",
    },
  ],
  catch_rate: 0.9,
};
