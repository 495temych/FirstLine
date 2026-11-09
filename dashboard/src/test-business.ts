import type { BusinessCase, Layer } from "./api";

const layer: Layer = {
  n: 129,
  share: 0.71,
  share_margin: 0.08,
  review_minutes: 2,
  model_chf: 0.005,
  bill_chf: 77.2,
  catch_rate: 0.9,
  mistakes_chf: 7.72,
  break_even: 0.133,
  catch_needed: 0.887,
  minutes_saved: 8.7,
  time_chf: 8.7,
  net_chf: 0.97,
  net_low: -0.19,
  net_high: 2.13,
  per_year_chf: 1458,
  net_none_caught: -68.5,
  net_all_caught: 8.69,
};

export const business: BusinessCase = {
  assumptions: {
    minutes_by_hand: 15,
    chf_per_hour: 60,
    catch_rate: 0.9,
    review_minutes: 2,
    tickets_per_year: 1500,
    mistakes: { security: 2000, wrong: 120, minor: 60 },
  },
  rates: { minutes_by_hand: 15, chf_per_hour: 60, catch_rate: 0.9 },
  projected: {
    ...layer,
    source: "20261108T010442-dev-rescored",
    model: "claude-haiku-4-5-20251001",
  },
  observed: {
    ...layer,
    n: 16,
    share: 0.94,
    review_minutes: 1.32,
    catch_rate: 0,
    mistakes_chf: 63.75,
    net_chf: -51.01,
    catch_needed: 0.8,
    wrong: 9,
    slipped: 9,
  },
};

export const losing: BusinessCase = {
  ...business,
  projected: business.projected && {
    ...business.projected,
    net_chf: -5,
    per_year_chf: -7500,
    catch_needed: 1.2,
  },
  observed: null,
};
