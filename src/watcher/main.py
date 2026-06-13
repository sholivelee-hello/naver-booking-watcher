"""감시 오케스트레이션."""
import logging
import os
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


def run_loop(cfg) -> None:
    """무한 루프: poll_interval마다 run_once. 에러 격리 + 연속실패 경고."""
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
        time.sleep(cfg.poll_interval)


def main() -> None:
    from watcher.config import load_config
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config(os.environ)
    log.info("감시 시작: %s, %d초 주기", cfg.booking_url, cfg.poll_interval)
    run_loop(cfg)


if __name__ == "__main__":
    main()
