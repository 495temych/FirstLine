"""Settings and paths."""

from agent import config


def test_the_default_model_applies_when_unset(monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert config.model_name() == config.DEFAULT_MODEL


def test_a_blank_model_name_counts_as_unset(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "")
    assert config.model_name() == config.DEFAULT_MODEL


def test_model_name_overrides_the_default(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5-5")
    assert config.model_name() == "claude-sonnet-5-5"


def test_usage_files_stay_at_the_repo_root():
    assert config.LOG_FILE == config.ROOT / "logs.csv"
    assert (config.ROOT / "pyproject.toml").exists()


def test_cost_uses_the_price_table():
    cost = config.cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert cost == 6.0


def test_a_model_with_no_price_has_no_cost():
    assert config.cost_usd("unpriced", 100, 100) is None
