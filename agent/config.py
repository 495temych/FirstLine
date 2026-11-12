"""Paths and settings, in one place."""

import os
from pathlib import Path
from typing import Literal, cast, get_args

from dotenv import load_dotenv

from agent.models import MODELS

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "kb"
# The usage log before Supabase. Only the Langfuse upload reads it now.
LOG_FILE = ROOT / "logs.csv"
USERS_FILE = ROOT / "data" / "records" / "users.json"
TICKETS_DIR = ROOT / "data" / "tickets"
# Each imported ticket's recorded checks, by playbook step. Built by evals.build_checks.
CHECKS_FILE = TICKETS_DIR / "checks.json"
# The knowledge base split's closed tickets and how they ended, for similar incidents.
PAST_TICKETS_FILE = TICKETS_DIR / "past_tickets.json"
EVALS_DIR = ROOT / "data" / "evals"
SOURCE_DIR = ROOT / "labs" / "synthetic_tickets"
DEFAULT_MODEL = "google/gemini-3.1-flash-lite"  # the owner's choice, docs/DECISIONS.md

USD_TO_CHF = 0.80  # an assumption, for showing model cost in francs

# How the agent works a ticket: one model call, or a loop of read-only lookups first.
Design = Literal["one call", "loop"]
DESIGNS: tuple[Design, ...] = get_args(Design)
DEFAULT_DESIGN: Design = "one call"
# The Assistant shows each step as it happens, so it runs the loop, before 7b measures
# it (docs/DECISIONS.md). The Queue and evaluations use DESIGN.
ASSISTANT_DESIGN: Design = "loop"
# The loop's limits, per ticket. At either one it stops and escalates what it found.
MAX_LOOKUPS = 6
MAX_LOOP_CHF = 0.01

# US dollars per million tokens: (input, output). The models are in agent/models.py.
PRICES = {name: model.price for name, model in MODELS.items()}

load_dotenv(ROOT / ".env")


def model_name() -> str:
    """Return the model in MODEL_NAME, or the default if it is unset or blank."""
    return os.getenv("MODEL_NAME") or DEFAULT_MODEL


def design() -> Design:
    """Return the design in DESIGN, or the default if it is unset or blank."""
    chosen = os.getenv("DESIGN") or DEFAULT_DESIGN
    if chosen not in DESIGNS:
        raise ValueError(f"DESIGN must be one of {', '.join(DESIGNS)}, not {chosen!r}.")
    return cast(Design, chosen)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Return what a call cost, or None if the model has no price."""
    if model not in PRICES:
        return None
    input_price, output_price = PRICES[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
