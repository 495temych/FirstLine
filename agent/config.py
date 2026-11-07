"""Paths and settings, in one place."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "kb"
LOG_FILE = ROOT / "logs.csv"
CHECKPOINT_DB = ROOT / "checkpoints.sqlite"
USERS_FILE = ROOT / "data" / "records" / "users.json"
TICKETS_DIR = ROOT / "data" / "tickets"
EVALS_DIR = ROOT / "data" / "evals"
SOURCE_DIR = ROOT / "labs" / "synthetic_tickets"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# US dollars per million tokens: (input, output).
PRICES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}

load_dotenv(ROOT / ".env")


def model_name() -> str:
    """Return the model in MODEL_NAME, or the default if it is unset or blank."""
    return os.getenv("MODEL_NAME") or DEFAULT_MODEL


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Return what a call cost, or None if the model has no price."""
    if model not in PRICES:
        return None
    input_price, output_price = PRICES[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
