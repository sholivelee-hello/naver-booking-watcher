"""텔레그램 알림 전송."""
import logging
import time

import requests

log = logging.getLogger("watcher.notifier")


def build_message(available_date: str, booking_url: str) -> str:
    """예약 가능 날짜를 사람이 읽을 메시지로 변환.

    링크는 해당 날짜로 바로 가도록 startDate 를 붙인다 → 누르면 그날 비어있는
    시간이 바로 보인다.
    """
    sep = "&" if "?" in booking_url else "?"
    dated_link = f"{booking_url}{sep}startDate={available_date}"
    return (
        "🏥 [병원예약] 예약 자리가 났어요!\n\n"
        f"📅 예약 가능일: {available_date}\n"
        "👇 누르면 그날 비어있는 시간이 바로 보여요\n"
        f"{dated_link}"
    )


def send_telegram(token: str, chat_id: str, text: str,
                  retries: int = 3, backoff: float = 2.0) -> bool:
    """텔레그램으로 메시지 전송. 실패 시 retries회 재시도. 성공=True.

    재시도 사이에 backoff초 대기한다(연속 실패가 순간 폭주로 소진되지 않게,
    예: 텔레그램 429 레이트리밋). 마지막 시도 뒤에는 대기하지 않는다.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff)
    log.warning("텔레그램 전송 %d회 모두 실패: %s", retries, last_exc)
    return False
