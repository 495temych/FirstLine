"""Paths and settings, in one place."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "kb"
LOG_FILE = ROOT / "logs.csv"
CHECKPOINT_DB = ROOT / "checkpoints.sqlite"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

load_dotenv(ROOT / ".env")


def model_name() -> str:
    """Return the model in MODEL_NAME, or the default if it is unset or blank."""
    return os.getenv("MODEL_NAME") or DEFAULT_MODEL
