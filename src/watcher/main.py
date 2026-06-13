"""감시 오케스트레이션."""
import logging
import os
import sys
import time

from watcher.availability import detect_new_availability
from watcher.naver_client import fetch_available_start_date
from watcher.notifier import build_message, send_telegram
from watcher.state_store import load_state, save_state

log = logging.getLogger("watcher")

FAIL_ALERT_THRESHOLD = 10
_STATE_KEY = "availableStartDate"


def run_once(cfg):
    """한 주기 실행: 조회→전환 판정→알림→상태저장. 새로 난 날짜(또는 None) 반환."""
    cur = fetch_available_start_date(cfg.business_id, cfg.biz_item_id)
    # 최초 실행(상태 파일 없음)에는 현재 값을 알림 없이 시드만 한다.
    # 이 분기가 없으면 첫 실행에서 이미 예약 가능한 상태일 때 곧바로 알림을
    # 보낸다. 다음 실행부터 마감→오픈 전환을 정상 감지한다.
    first_run = not os.path.exists(cfg.state_file)
    prev = load_state(cfg.state_file).get(_STATE_KEY)
    new = None if first_run else detect_new_availability(prev, cur)
    if new:
        log.info("예약 자리 발생: %s", new)
        msg = build_message(new, cfg.booking_url)
        send_telegram(cfg.bot_token, cfg.chat_id, msg)
    save_state(cfg.state_file, {_STATE_KEY: cur})
    return new


def run_loop(cfg, max_seconds=None) -> None:
    """poll_interval마다 run_once. 에러 격리 + 연속실패 경고.

    max_seconds 가 주어지면 그 시간이 지나면 종료한다(GitHub Actions처럼
    외부에서 주기적으로 재실행하는 경우). None 이면 무한 루프(상시 실행).
    """
    deadline = None if max_seconds is None else time.monotonic() + max_seconds
    consecutive_failures = 0
    alerted = False
    while True:
        try:
            run_once(cfg)
            consecutive_failures = 0
            if alerted:
                send_telegram(cfg.bot_token, cfg.chat_id, "✅ 감시 정상 복구됨")
                alerted = False
        except Exception as e:  # 루프는 절대 죽지 않음
            consecutive_failures += 1
            log.warning("조회 실패 (%d회 연속): %s", consecutive_failures, e)
            if consecutive_failures >= FAIL_ALERT_THRESHOLD and not alerted:
                send_telegram(
                    cfg.bot_token, cfg.chat_id,
                    f"⚠️ 감시 중단 위험: {consecutive_failures}회 연속 조회 실패",
                )
                alerted = True
        if deadline is not None and time.monotonic() >= deadline:
            return
        time.sleep(cfg.poll_interval)


def main() -> None:
    """엔트리포인트.

    모드:
    - 기본: 무한 루프(상시 실행: Mac/Oracle)
    - `--once`: 1회만 실행하고 종료
    - `--minutes N`: N분 동안 poll_interval 주기로 돌고 종료
      (GitHub Actions에서 한 회차 안에서 60초마다 반복할 때 사용)
    """
    from watcher.config import load_config
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config(os.environ)
    args = sys.argv[1:]
    if "--once" in args:
        log.info("감시 1회 실행: %s", cfg.booking_url)
        run_once(cfg)
        return
    if "--minutes" in args:
        minutes = int(args[args.index("--minutes") + 1])
        log.info("감시 %d분간 실행: %s (%d초 주기)",
                 minutes, cfg.booking_url, cfg.poll_interval)
        run_loop(cfg, max_seconds=minutes * 60)
        return
    log.info("감시 시작: %s, %d초 주기", cfg.booking_url, cfg.poll_interval)
    run_loop(cfg)


if __name__ == "__main__":
    main()
