import pytest

from watcher.config import load_config, ConfigError


def _env(**overrides):
    base = {
        "TELEGRAM_BOT_TOKEN": "tok",
        "TELEGRAM_CHAT_ID": "chat",
        "NAVER_BUSINESS_ID": "597072",
        "NAVER_BIZ_ITEM_ID": "5011045",
    }
    base.update(overrides)
    return base


def test_load_config_reads_values_and_defaults():
    cfg = load_config(_env())
    assert cfg.bot_token == "tok"
    assert cfg.business_id == "597072"
    assert cfg.poll_interval == 60
    assert cfg.state_file == "state.json"


def test_load_config_overrides_defaults():
    cfg = load_config(_env(POLL_INTERVAL_SECONDS="30"))
    assert cfg.poll_interval == 30


def test_load_config_missing_required_raises():
    env = _env()
    del env["TELEGRAM_BOT_TOKEN"]
    with pytest.raises(ConfigError):
        load_config(env)
