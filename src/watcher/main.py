"""감시 오케스트레이션."""
import logging
import os
import time
from datetime import date, timedelta

from watcher.availability import compute_open_slots, newly_opened
from watcher.naver_client import fetch_daily
from watcher.notifier import build_message, send_telegram
from watcher.state_store import load_state, save_state

log = logging.getLogger("watcher")

FAIL_ALERT_THRESHOLD = 10


def run_once(cfg, start_date: str, end_date: str) -> dict:
    """한 주기 실행: 조회→판정→신규오픈 비교→알림→상태저장. 신규오픈 맵 반환."""
    raw = fetch_daily(cfg.business_id, cfg.biz_item_id, start_date, end_date)
    cur = compute_open_slots(raw)
    prev = load_state(cfg.state_file)
    new = newly_opened(prev, cur)
    if new:
        log.info("신규 빈자리 %d건: %s", len(new), new)
        msg = build_message(new, cfg.booking_url)
        send_telegram(cfg.bot_token, cfg.chat_id, msg)
    save_state(cfg.state_file, cur)
    return new


def date_range(today: date, watch_days: int):
    """오늘부터 watch_days일 후까지의 (start, end) "YYYY-MM-DD" 문자열."""
    start = today
    end = today + timedelta(days=watch_days)
    return start.isoformat(), end.isoformat()


def run_loop(cfg) -> None:
    """무한 루프: poll_interval마다 run_once. 에러 격리 + 연속실패 경고."""
    consecutive_failures = 0
    alerted = False
    while True:
        try:
            start, end = date_range(date.today(), cfg.watch_days)
            run_once(cfg, start, end)
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
        time.sleep(cfg.poll_interval)


def main() -> None:
    from watcher.config import load_config
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config(os.environ)
    log.info("감시 시작: %s, %d일 범위, %d초 주기",
             cfg.booking_url, cfg.watch_days, cfg.poll_interval)
    run_loop(cfg)


if __name__ == "__main__":
    main()
