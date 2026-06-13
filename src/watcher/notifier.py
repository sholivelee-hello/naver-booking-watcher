"""텔레그램 알림 전송."""
import requests


def build_message(available_date: str, booking_url: str) -> str:
    """예약 가능 날짜를 사람이 읽을 메시지로 변환."""
    return (
        "🏥 [병원예약] 예약 자리가 났어요!\n\n"
        f"📅 가장 빠른 예약 가능일: {available_date}\n\n"
        f"👉 지금 바로 예약: {booking_url}"
    )


def send_telegram(token: str, chat_id: str, text: str, retries: int = 3) -> bool:
    """텔레그램으로 메시지 전송. 실패 시 retries회 재시도. 성공=True."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    for _ in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            continue
    return False
