from unittest.mock import patch

from watcher.config import Config
from watcher.main import run_once


def _cfg(tmp_path):
    return Config(
        bot_token="tok", chat_id="chat",
        business_id="597072", biz_item_id="5011045",
        poll_interval=60, watch_days=60,
        state_file=str(tmp_path / "state.json"),
    )


def test_run_once_notifies_on_new_open(tmp_path):
    cfg = _cfg(tmp_path)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 45, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {"2026-06-20": 3}
    assert send.called


def test_run_once_no_notify_when_already_open(tmp_path):
    cfg = _cfg(tmp_path)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 45, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True):
        run_once(cfg, "2026-06-13", "2026-08-12")
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send2:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {}
    assert not send2.called


def test_run_once_skips_send_when_no_open(tmp_path):
    cfg = _cfg(tmp_path)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 48, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {}
    assert not send.called


from datetime import date
from watcher.main import date_range


def test_date_range_spans_watch_days():
    start, end = date_range(date(2026, 6, 13), watch_days=60)
    assert start == "2026-06-13"
    assert end == "2026-08-12"
