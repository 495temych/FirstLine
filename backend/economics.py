"""What FirstLine is worth, in CHF: the one place for `docs/BUSINESS_GOAL.md`'s sums.

    minutes saved = share approved × minutes by hand − minutes to review
    net saving    = minutes saved × rate per minute − model cost − cost of mistakes

Every decision is reviewed, so a wrong one costs money only when the technician
misses it. Projected uses the latest development evaluation, with review time and
the share of mistakes caught assumed. Observed uses the Queue's real reviews, where
both are measured: the labels say which approved decisions were wrong.
"""

from functools import cache
from typing import Annotated

from fastapi import APIRouter, Query

from backend import queue_board
from evals import runner, scoring

MINUTES_BY_HAND = 15  # a first pass by hand, assumed: the records have no times
REVIEW_MINUTES = 2  # reviewing one decision, assumed until reviews are measured
CATCH_RATE = 0.9  # wrong decisions a technician catches in review, assumed
CHF_PER_HOUR = 60
TICKETS_PER_YEAR = 1500  # 745 tickets in six months, in the dataset
EVAL_SET = "dev"  # the main exam: every path, and the set the Queue draws from

ASSUMPTIONS = {
    "minutes_by_hand": MINUTES_BY_HAND,
    "review_minutes": REVIEW_MINUTES,
    "chf_per_hour": CHF_PER_HOUR,
    "catch_rate": CATCH_RATE,
    "tickets_per_year": TICKETS_PER_YEAR,
    "mistakes": {
        "security": scoring.COST_SECURITY,
        "wrong": scoring.COST_WRONG,
        "minor": scoring.COST_MINOR,
    },
}


def net(
    share: float,
    review_minutes: float,
    costs: tuple[float, float],
    minutes_by_hand: float = MINUTES_BY_HAND,
    chf_per_hour: float = CHF_PER_HOUR,
) -> dict:
    """Net saving per ticket, from the share approved unchanged. `costs` is the
    model cost and the mistakes' cost per ticket, in CHF.
    """
    model_chf, mistakes_chf = costs
    minutes_saved = share * minutes_by_hand - review_minutes
    time_chf = minutes_saved * chf_per_hour / 60
    return {
        "minutes_saved": minutes_saved,
        "time_chf": time_chf,
        "net_chf": time_chf - model_chf - mistakes_chf,
    }


def break_even(
    review_minutes: float, minutes_by_hand: float = MINUTES_BY_HAND
) -> float:
    """The share approved unchanged at which review time and saved time are equal."""
    return review_minutes / minutes_by_hand


def catch_needed(time_chf: float, model_chf: float, bill_chf: float) -> float | None:
    """The share of wrong decisions technicians must catch for the saving to stay
    above zero. Above 1, even catching every one doesn't pay. None with no mistakes.
    """
    if bill_chf == 0:
        return None
    return max(1 - (time_chf - model_chf) / bill_chf, 0.0)


def _layer(counted: dict, rates: dict) -> dict:
    """One way of counting, with the saving at either end of the share's margin.

    `counted` has the share approved unchanged and its n, review minutes, model
    cost, the bill if no mistake were caught, and the share technicians catch.
    """
    share, n, review = counted["share"], counted["n"], counted["review_minutes"]
    missed = (1 - counted["catch_rate"]) * counted["bill_chf"]
    costs = (counted["model_chf"], missed)
    spread = scoring.margin(share, n)
    low, high = max(share - spread, 0.0), min(share + spread, 1.0)
    saved = net(share, review, costs, **rates)
    return {
        **counted,
        "share_margin": spread,
        "mistakes_chf": missed,
        "break_even": break_even(review, rates["minutes_by_hand"]),
        "catch_needed": catch_needed(
            saved["time_chf"], counted["model_chf"], counted["bill_chf"]
        ),
        **saved,
        "net_low": net(low, review, costs, **rates)["net_chf"],
        "net_high": net(high, review, costs, **rates)["net_chf"],
        "per_year_chf": saved["net_chf"] * TICKETS_PER_YEAR,
        # Net saving is a straight line in the share caught, so its two ends draw it.
        "net_none_caught": saved["time_chf"]
        - counted["model_chf"]
        - counted["bill_chf"],
        "net_all_caught": saved["time_chf"] - counted["model_chf"],
    }


def projected(catch_rate: float = CATCH_RATE, **rates) -> dict | None:
    """From the default model's latest full development evaluation. A decision right
    in full counts as approved unchanged, and a wrong one costs its price unless a
    technician catches it, at the assumed rate. Other models' runs are the benchmark's.
    """
    run = next((r for r in runner.default_runs() if r["set"] == EVAL_SET), None)
    if run is None:
        return None
    layer = from_summary(run["summary"], catch_rate, **rates)
    return {**layer, "source": run["id"], "model": run["model"]}


def from_summary(
    s: dict,
    catch_rate: float = CATCH_RATE,
    minutes_by_hand: float = MINUTES_BY_HAND,
    chf_per_hour: float = CHF_PER_HOUR,
) -> dict:
    """Net saving per ticket from an evaluation's summary, or a yardstick's, which
    has no model cost.
    """
    counted = {
        "share": s["action_accuracy"],
        "n": s["n"],
        "review_minutes": REVIEW_MINUTES,
        "model_chf": s.get("cost_per_ticket_chf") or 0.0,
        "bill_chf": s["mistake_cost_chf"] / s["n"],
        "catch_rate": catch_rate,
    }
    rates = {"minutes_by_hand": minutes_by_hand, "chf_per_hour": chf_per_hour}
    return _layer(counted, rates)


@cache
def _answers() -> dict[str, dict]:
    return {t["id"]: a for t, a in runner.load_imported(queue_board.SOURCE_SPLIT)}


def _price(ticket: dict) -> int:
    """What a reviewed decision would cost if it ran, by the labels. 0 when right."""
    answer = _answers().get(ticket["id"])
    decision = ticket["decision"]
    if answer is None or decision is None:
        return 0
    return scoring.mistake_cost(
        answer, decision["path"], decision["tool"], decision["queue"]
    )


def observed(tickets: list[dict], **rates) -> dict | None:
    """From the Queue's reviews: what technicians approved, how long they took, and
    how many wrong decisions they caught. Only the approved ones are priced.
    """
    reviewed = [t for t in tickets if t["review"]]
    if not reviewed:
        return None
    n = len(reviewed)
    wrong = [(t, cost) for t in reviewed if (cost := _price(t))]
    slipped = [cost for t, cost in wrong if t["review"]["verdict"] == "approved"]
    approved = sum(t["review"]["verdict"] == "approved" for t in reviewed)
    counted = {
        "share": approved / n,
        "n": n,
        "review_minutes": sum(t["review"]["seconds"] for t in reviewed) / n / 60,
        "model_chf": sum(t["cost_chf"] or 0 for t in reviewed) / n,
        "bill_chf": sum(cost for _, cost in wrong) / n,
        "catch_rate": 1 - len(slipped) / len(wrong) if wrong else 1.0,
    }
    return {**_layer(counted, rates), "wrong": len(wrong), "slipped": len(slipped)}


router = APIRouter()


@router.get("/api/business", operation_id="read_business_case")
def read_business_case(
    minutes_by_hand: Annotated[float, Query(gt=0, le=120)] = MINUTES_BY_HAND,
    chf_per_hour: Annotated[float, Query(gt=0, le=500)] = CHF_PER_HOUR,
    catch_rate: Annotated[float, Query(ge=0, le=1)] = CATCH_RATE,
) -> dict:
    """Is it worth it? Net saving per ticket, projected and observed, for any
    minutes by hand, hourly rate and share of mistakes caught.
    """
    rates = {"minutes_by_hand": minutes_by_hand, "chf_per_hour": chf_per_hour}
    return {
        "assumptions": ASSUMPTIONS,
        "rates": {**rates, "catch_rate": catch_rate},
        "projected": projected(catch_rate, **rates),
        "observed": observed(queue_board.board.view()["tickets"], **rates),
    }
