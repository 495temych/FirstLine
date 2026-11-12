"""The models FirstLine can run on, and the client for each.

Claude goes to Anthropic and OpenAI's own models to OpenAI, each on its own key. Every
other model goes through OpenRouter, pinned to one provider so a result can be
repeated and its data path is known. Every model gets the same instructions and the
same forced decision tool, at the lowest reasoning effort it offers.
"""

import os
from dataclasses import dataclass
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

OPENROUTER_URL = "https://openrouter.ai/api/v1"
MAX_TOKENS = 2048

Lab = Literal["anthropic", "openai", "openrouter"]


@dataclass(frozen=True)
class Model:
    """One model: who serves it, its price and how it's asked."""

    lab: Lab
    price: tuple[float, float]  # US dollars per million tokens, input and output
    effort: str | None = None  # the lowest reasoning effort it accepts
    provider: str | None = None  # the OpenRouter provider it's pinned to
    region: str = "US"  # where the prompt is processed, or "unconfirmed"
    free: bool = False  # a free variant: smoke tests only, and it may keep prompts
    forced: bool = True  # False where no provider can force the decision tool


# Prices from each lab's or OpenRouter's list on 2026-11-09.
MODELS: dict[str, Model] = {
    "claude-haiku-4-5-20251001": Model("anthropic", (1.00, 5.00)),
    "claude-haiku-5-5": Model("anthropic", (0.10, 0.50)),
    "claude-sonnet-5-5": Model("anthropic", (2.00, 10.00)),
    "gpt-6-luna": Model("openai", (0.10, 0.50), effort="none"),
    "gpt-5-nano": Model("openai", (0.05, 0.40), effort="minimal"),
    "gpt-6.1-terra": Model("openai", (1.00, 5.00), effort="none"),
    "openai/gpt-oss-120b": Model(
        "openrouter", (0.037, 0.17), effort="low", provider="deepinfra/bf16"
    ),
    "google/gemini-3.1-flash-lite": Model(
        "openrouter",
        (0.275, 1.65),
        effort="minimal",
        provider="google-vertex/eu",
        region="EU",
    ),
    "mistralai/mistral-small-2603": Model(
        "openrouter", (0.165, 0.66), provider="mistral/eu", region="EU"
    ),
    "deepseek/deepseek-v4.1-flash": Model(
        "openrouter", (0.30, 1.20), effort="none", provider="fireworks"
    ),
    "qwen/qwen3.7-flash": Model(
        "openrouter",
        (0.03, 0.13),
        effort="none",
        provider="alibaba",
        region="unconfirmed",
        forced=False,
    ),
    # GLM can't turn reasoning off, so it thinks as little as it allows.
    "z-ai/glm-5.3-flash": Model(
        "openrouter", (0.15, 0.50), effort="minimal", provider="together"
    ),
    "nvidia/nemotron-3.5-lightning:free": Model(
        "openrouter", (0.0, 0.0), region="unconfirmed", free=True
    ),
    "google/gemma-4-26b-a4b-it:free": Model(
        "openrouter", (0.0, 0.0), region="unconfirmed", free=True
    ),
}


# What a person calls each model.
LABELS = {
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "claude-haiku-5-5": "Claude Haiku 5.5",
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "gpt-6-luna": "GPT-6 Luna",
    "gpt-5-nano": "GPT-5 nano",
    "gpt-6.1-terra": "GPT-6.1 Terra",
    "openai/gpt-oss-120b": "gpt-oss-120b",
    "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "mistralai/mistral-small-2603": "Mistral Small",
    "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
    "qwen/qwen3.7-flash": "Qwen 3.7 Flash",
    "z-ai/glm-5.3-flash": "GLM 5.3 Flash",
    "nvidia/nemotron-3.5-lightning:free": "Nemotron 3.5 Lightning (free)",
    "google/gemma-4-26b-a4b-it:free": "Gemma 4 26B (free)",
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def _openrouter_body(model: Model) -> dict:
    """OpenRouter's routing: one provider, no fallback, the tool call supported, and
    no provider that keeps prompts. Free variants can't promise that, so they skip it.
    """
    provider: dict = {"require_parameters": True}
    if model.provider:
        provider |= {"order": [model.provider], "allow_fallbacks": False}
    if not model.free:
        provider["data_collection"] = "deny"
    body: dict = {"provider": provider, "usage": {"include": True}}
    if model.effort:
        body["reasoning"] = {"effort": model.effort}
    return body


def chat_model(name: str) -> BaseChatModel:
    """The client for a model. An unknown name is treated as a Claude model.

    max_retries=0: transient errors are retried by the graph's RetryPolicy, not twice
    over by the SDK as well.
    """
    model = MODELS.get(name, Model("anthropic", (0.0, 0.0)))
    settings: dict[str, Any] = {"model": name, "max_retries": 0}
    if model.lab == "anthropic":
        anthropic_settings: dict[str, Any] = {**settings, "max_tokens": MAX_TOKENS}
        return ChatAnthropic(**anthropic_settings)
    settings["max_completion_tokens"] = MAX_TOKENS
    if model.lab == "openai":
        return ChatOpenAI(**settings, reasoning_effort=model.effort)
    return ChatOpenAI(
        **settings,
        base_url=OPENROUTER_URL,
        api_key=SecretStr(os.environ.get("OPENROUTER_API_KEY", "")),
        extra_body=_openrouter_body(model),
    )


def tool_choice(name: str, tool: str) -> str:
    """Force the decision tool, or only offer it where no provider can force it.
    A model that then answers without it has made an invalid decision.
    """
    model = MODELS.get(name)
    return tool if model is None or model.forced else "auto"


def any_tool(name: str) -> str:
    """Make the model call one of its tools each turn, or only offer them where no
    provider can force a call. A turn with no call then counts as no decision."""
    model = MODELS.get(name)
    return "any" if model is None or model.forced else "auto"


def price(name: str) -> tuple[float, float] | None:
    model = MODELS.get(name)
    return None if model is None else model.price
