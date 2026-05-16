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


def test_config_loads_meta_page_id(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("META_PAGE_ID", "123456789")
    monkeypatch.setenv("META_IG_USER_ID", "987654321")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://fleet.nayzfreedom.cloud")
    cfg = Config.from_env()
    assert cfg.meta_page_id == "123456789"
    assert cfg.meta_ig_user_id == "987654321"
    assert cfg.public_base_url == "https://fleet.nayzfreedom.cloud"


def test_config_meta_fields_default_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.delenv("META_PAGE_ID", raising=False)
    monkeypatch.delenv("META_IG_USER_ID", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("OPS_PUBLIC_BASE_URL", raising=False)
    cfg = Config.from_env()
    assert cfg.meta_page_id == ""
    assert cfg.meta_ig_user_id == ""
    assert cfg.public_base_url == "https://fleet.nayzfreedom.cloud"
