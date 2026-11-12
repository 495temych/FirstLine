"""Which client serves each model, and how OpenRouter is told to route it."""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from agent import config, models


def test_claude_goes_to_anthropic():
    assert isinstance(models.chat_model("claude-haiku-4-5-20251001"), ChatAnthropic)


def test_an_unknown_model_is_treated_as_claude():
    assert isinstance(models.chat_model("claude-future"), ChatAnthropic)


def test_openai_models_go_to_openai_at_their_lowest_effort():
    llm = models.chat_model("gpt-5-nano")
    assert isinstance(llm, ChatOpenAI)
    assert llm.openai_api_base is None
    assert llm.reasoning_effort == "minimal"


def test_other_models_go_through_openrouter_pinned_to_one_provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    llm = models.chat_model("mistralai/mistral-small-2603")
    assert isinstance(llm, ChatOpenAI)
    assert llm.openai_api_base == models.OPENROUTER_URL
    provider = (llm.extra_body or {})["provider"]
    assert provider["order"] == ["mistral/eu"]
    assert provider["allow_fallbacks"] is False
    assert provider["require_parameters"] is True
    assert provider["data_collection"] == "deny"


def test_free_variants_skip_the_data_promise_they_cant_keep():
    body = models._openrouter_body(models.MODELS["google/gemma-4-26b-a4b-it:free"])
    assert "data_collection" not in body["provider"]
    assert "order" not in body["provider"]
    assert "reasoning" not in body


def test_openrouter_asks_for_the_lowest_effort_and_the_cost():
    body = models._openrouter_body(models.MODELS["openai/gpt-oss-120b"])
    assert body["reasoning"] == {"effort": "low"}
    assert body["usage"] == {"include": True}


def test_every_model_has_a_price_and_a_region():
    for name, model in models.MODELS.items():
        assert config.PRICES[name] == model.price
        assert model.region
        assert models.price(name) == model.price
    assert models.price("unknown") is None


def test_the_decision_tool_is_forced_unless_no_provider_can():
    assert models.tool_choice("gpt-5-nano", "record") == "record"
    assert models.tool_choice("claude-future", "record") == "record"
    assert models.tool_choice("qwen/qwen3.7-flash", "record") == "auto"


def test_every_model_has_a_name_a_person_would_use():
    assert set(models.LABELS) == set(models.MODELS)
    assert models.label("gpt-6-luna") == "GPT-6 Luna"
    assert models.label("unknown") == "unknown"


def test_the_loop_forces_some_call_where_the_provider_can():
    assert models.any_tool("gpt-5-nano") == "any"
    assert models.any_tool("claude-future") == "any"
    assert models.any_tool("qwen/qwen3.7-flash") == "auto"
