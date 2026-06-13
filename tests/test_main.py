import os

import pytest
from unittest.mock import patch

from watcher.config import Config
from watcher.main import run_loop, run_once
from watcher.state_store import save_state


def _cfg(tmp_path):
    return Config(
        bot_token="tok", chat_id="chat",
        business_id="597072", biz_item_id="5011045",
        poll_interval=60, watch_days=60,
        state_file=str(tmp_path / "state.json"),
    )


def test_run_once_notifies_on_new_open(tmp_path):
    cfg = _cfg(tmp_path)
    # 상태 파일을 미리 만들어 두면(빈 상태) 최초 실행 시드 분기를 건너뛰고
    # 열린 날짜가 진짜 신규 전환으로 판정되어 알림이 발송된다.
    save_state(cfg.state_file, {})
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 45, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {"2026-06-20": 3}
    assert send.called


def test_run_once_first_run_seeds_silently(tmp_path):
    cfg = _cfg(tmp_path)
    assert not os.path.exists(cfg.state_file)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 45, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {}
    assert not send.called
    # 상태가 시드되어 다음 실행부터 전환을 감지할 수 있어야 한다.
    assert os.path.exists(cfg.state_file)


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


class _StopLoop(Exception):
    """무한 루프를 제어된 시점에 빠져나오기 위한 센티넬."""


def test_run_loop_alerts_after_threshold_failures(tmp_path):
    cfg = _cfg(tmp_path)
    # time.sleep을 사이클 카운터로 사용: 10번째 사이클의 sleep에서 루프 탈출.
    # run_once가 매번 실패하므로 10회째에 경고 알림이 정확히 한 번 발송된다.
    sleeps = [None] * 9 + [_StopLoop()]
    with patch("watcher.main.run_once", side_effect=RuntimeError("boom")), \
         patch("watcher.main.send_telegram", return_value=True) as send, \
         patch("watcher.main.time.sleep", side_effect=sleeps):
        with pytest.raises(_StopLoop):
            run_loop(cfg)
    assert send.call_count == 1
    warning_text = send.call_args.args[2]
    assert "감시 중단 위험" in warning_text


def test_run_loop_sends_recovery_after_alert(tmp_path):
    cfg = _cfg(tmp_path)
    # 10회 실패(10회째에 경고) 후 11회째 성공 → 복구 알림.
    # sleep은 11번째 사이클 직후 루프를 끝낸다.
    run_results = [RuntimeError("boom")] * 10 + [None]
    sleeps = [None] * 10 + [_StopLoop()]
    with patch("watcher.main.run_once", side_effect=run_results), \
         patch("watcher.main.send_telegram", return_value=True) as send, \
         patch("watcher.main.time.sleep", side_effect=sleeps):
        with pytest.raises(_StopLoop):
            run_loop(cfg)
    texts = [c.args[2] for c in send.call_args_list]
    assert any("감시 중단 위험" in t for t in texts)
    assert any("정상 복구" in t for t in texts)
