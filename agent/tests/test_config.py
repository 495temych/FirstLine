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
    assert config.CHECKPOINT_DB == config.ROOT / "checkpoints.sqlite"
    assert (config.ROOT / "pyproject.toml").exists()
