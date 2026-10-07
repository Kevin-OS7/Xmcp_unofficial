import pytest

from xmcp_unofficial import config
from xmcp_unofficial.config import Settings, parse_delay


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XMCP_CONFIG", str(tmp_path / "config.toml"))
    for k in ("XMCP_DB", "XMCP_PROXY", "XMCP_REQ_DELAY", "XMCP_TIMEOUT", "XMCP_MAX_LIMIT"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def test_parse_delay():
    assert parse_delay("1.5") == 1.5
    assert parse_delay("1-3") == (1.0, 3.0)
    assert parse_delay([2, 4]) == (2.0, 4.0)
    assert parse_delay(0) is None
    for bad in ("abc", "-1", "3-1"):
        with pytest.raises(ValueError):
            parse_delay(bad)


def test_defaults():
    s = Settings.from_env()
    assert s.req_delay == 1.5
    assert s.timeout == 120
    assert s.proxy is None


def test_file_then_env_precedence(monkeypatch):
    config.write_file({"req_delay": "2-5", "timeout": 60, "proxy": 'http://u:p"w@h:1'})
    s = Settings.from_env()
    assert s.req_delay == (2.0, 5.0)
    assert s.timeout == 60
    assert s.proxy == 'http://u:p"w@h:1'

    monkeypatch.setenv("XMCP_REQ_DELAY", "0")
    monkeypatch.setenv("XMCP_TIMEOUT", "30")
    s = Settings.from_env()
    assert s.req_delay is None
    assert s.timeout == 30


def test_config_file_is_private():
    path = config.write_file({"req_delay": "1.5"})
    assert path.stat().st_mode & 0o077 == 0


async def test_setup_wizard_registers_account(isolated, monkeypatch):
    from xmcp_unofficial import setup_wizard

    monkeypatch.setenv("XMCP_DB", str(isolated / "accounts.db"))
    answers = iter(["y", "@reader", "", "n", "2-4", "n"])
    secrets = iter(["auth_token=abc ;ct0=def"])
    await setup_wizard.run_setup(ask=lambda _: next(answers), secret=lambda _: next(secrets))

    s = Settings.from_env()
    assert s.req_delay == (2.0, 4.0)
    from xmcp_unofficial._vendor.twscrape import AccountsPool

    acc = await AccountsPool(str(s.db_path)).get("reader")
    assert acc.active and acc.cookies == {"auth_token": "abc", "ct0": "def"}
