import os
import pytest
from config import Config, MissingAPIKeyError


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    cfg = Config.from_env()
    assert cfg.anthropic_api_key == "test-key-123"
    assert cfg.brave_search_api_key == "brave-key"
    assert cfg.openai_api_key == "openai-key"


def test_config_raises_on_missing_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        Config.from_env()
