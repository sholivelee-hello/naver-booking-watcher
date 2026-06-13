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
        poll_interval=60,
        state_file=str(tmp_path / "state.json"),
    )


def test_run_once_notifies_when_slot_opens(tmp_path):
    cfg = _cfg(tmp_path)
    # 마감 상태(None)를 미리 시드해 두면, 날짜가 생기는 순간이 진짜 전환으로
    # 판정되어 알림이 발송된다.
    save_state(cfg.state_file, {"availableStartDate": None})
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-20"), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg)
    assert new == "2026-06-20"
    assert send.called
    assert "2026-06-20" in send.call_args.args[2]


def test_run_once_first_run_seeds_silently(tmp_path):
    cfg = _cfg(tmp_path)
    assert not os.path.exists(cfg.state_file)
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-20"), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg)
    assert new is None
    assert not send.called
    # 상태가 시드되어 다음 실행부터 전환을 감지할 수 있어야 한다.
    assert os.path.exists(cfg.state_file)


def test_run_once_no_notify_when_still_full(tmp_path):
    cfg = _cfg(tmp_path)
    # 첫 실행: 마감(None) 시드, 알림 없음. 둘째 실행: 여전히 마감 → 알림 없음.
    with patch("watcher.main.fetch_available_start_date", return_value=None), \
         patch("watcher.main.send_telegram", return_value=True):
        run_once(cfg)
    with patch("watcher.main.fetch_available_start_date", return_value=None), \
         patch("watcher.main.send_telegram", return_value=True) as send2:
        new = run_once(cfg)
    assert new is None
    assert not send2.called


def test_run_once_no_notify_when_date_unchanged(tmp_path):
    cfg = _cfg(tmp_path)
    save_state(cfg.state_file, {"availableStartDate": "2026-06-20"})
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-20"), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg)
    assert new is None
    assert not send.called


def test_run_once_notifies_when_earlier_date_appears(tmp_path):
    cfg = _cfg(tmp_path)
    save_state(cfg.state_file, {"availableStartDate": "2026-06-20"})
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-15"), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg)
    assert new == "2026-06-15"
    assert send.called


def test_run_once_raises_and_keeps_state_when_send_fails(tmp_path):
    cfg = _cfg(tmp_path)
    # 마감(None) 시드 후 자리가 났는데 텔레그램 전송이 실패하면, 상태를
    # 갱신하지 않아 다음 주기에 같은 전환을 다시 감지(재시도)할 수 있어야 하고,
    # NotifyError 로 올라가 run_loop 의 헬스 카운터에 반영돼야 한다.
    from watcher.main import NotifyError
    save_state(cfg.state_file, {"availableStartDate": None})
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-20"), \
         patch("watcher.main.send_telegram", return_value=False):
        with pytest.raises(NotifyError):
            run_once(cfg)
    from watcher.state_store import load_state
    # 상태는 여전히 마감(None) 그대로여야 한다 (날짜로 갱신되면 영영 누락됨).
    assert load_state(cfg.state_file).get("availableStartDate") is None


def test_run_once_corrupt_state_seeds_silently(tmp_path):
    cfg = _cfg(tmp_path)
    # 손상된 상태 파일: 첫 실행처럼 조용히 시드만 하고 알림은 보내지 않아야 한다.
    with open(cfg.state_file, "w", encoding="utf-8") as f:
        f.write("{ not valid json")
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-20"), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg)
    assert new is None
    assert not send.called


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


def test_run_loop_exits_after_max_seconds(tmp_path):
    cfg = _cfg(tmp_path)
    # monotonic: 시작=0 → deadline=300. 매 반복 끝 체크에서 60,120,180,240,300.
    # 5번째 반복 후 300>=300 이라 종료. run_once 5회 호출되어야 한다.
    times = [0, 60, 120, 180, 240, 300]
    with patch("watcher.main.run_once") as run_once_mock, \
         patch("watcher.main.send_telegram", return_value=True), \
         patch("watcher.main.time.sleep"), \
         patch("watcher.main.time.monotonic", side_effect=times):
        run_loop(cfg, max_seconds=300)
    assert run_once_mock.call_count == 5


def test_run_loop_counts_send_failures_toward_alert(tmp_path):
    cfg = _cfg(tmp_path)
    save_state(cfg.state_file, {"availableStartDate": None})
    # 조회는 매번 성공(자리 남)하지만 전송이 계속 실패 → run_once 가 NotifyError 를
    # 올려 헬스 카운터가 쌓이고, 임계치에서 '감시 중단 위험' 경고가 떠야 한다.
    # (조회는 되는데 전송만 실패하는 조용한 장애를 운영자가 알 수 있어야 함)
    sleeps = [None] * 9 + [_StopLoop()]
    with patch("watcher.main.fetch_available_start_date", return_value="2026-06-20"), \
         patch("watcher.main.send_telegram", return_value=False) as send, \
         patch("watcher.main.time.sleep", side_effect=sleeps):
        with pytest.raises(_StopLoop):
            run_loop(cfg)
    texts = [c.args[2] for c in send.call_args_list]
    assert any("감시 중단 위험" in t for t in texts)


def test_main_rejects_bad_minutes(monkeypatch):
    for k, v in {
        "TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "chat",
        "NAVER_BUSINESS_ID": "597072", "NAVER_BIZ_ITEM_ID": "5011045",
    }.items():
        monkeypatch.setenv(k, v)
    from watcher.main import main
    monkeypatch.setattr("sys.argv", ["prog", "--minutes", "abc"])
    with pytest.raises(SystemExit):
        main()
    # 값 자체가 빠진 경우도 깔끔히 종료해야 한다 (IndexError 크래시 아님)
    monkeypatch.setattr("sys.argv", ["prog", "--minutes"])
    with pytest.raises(SystemExit):
        main()


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
