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


def _retry_delay(exc, attempt: int, backoff: float) -> float:
    """다음 재시도까지 대기 시간(초).

    텔레그램 429(레이트리밋)면 응답의 Retry-After 헤더를 우선 존중한다 —
    고정 2초로 곧장 재시도하면 레이트리밋 창(보통 수십 초) 안에서 모두 실패해
    정작 자리 났을 때 알림을 잃는다. 그 외에는 지수 백오프(backoff*2^attempt).
    """
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) == 429:
        ra = resp.headers.get("Retry-After")
        if ra:
            try:
                return float(ra)
            except (TypeError, ValueError):
                pass
    return backoff * (2 ** attempt)


def send_telegram(token: str, chat_id: str, text: str,
                  retries: int = 3, backoff: float = 2.0) -> bool:
    """텔레그램으로 메시지 전송. 실패 시 retries회 재시도. 성공=True.

    재시도 사이 대기는 지수 백오프이며, 429면 Retry-After 헤더를 존중한다
    (_retry_delay 참고). 마지막 시도 뒤에는 대기하지 않는다.

    영구 오류(4xx, 단 429 제외 — 예: 400 chat not found, 401/403 토큰 문제)는
    재시도해도 절대 성공하지 못하므로 즉시 중단한다(재시도 낭비 방지).
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
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                log.warning("텔레그램 영구 오류 %s — 재시도 안 함: %s", status, e)
                return False
            if attempt < retries - 1:
                time.sleep(_retry_delay(e, attempt, backoff))
    log.warning("텔레그램 전송 %d회 모두 실패: %s", retries, last_exc)
    return False
