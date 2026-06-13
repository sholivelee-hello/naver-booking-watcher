"""텔레그램 알림 전송."""
import requests


def build_message(open_slots: dict, booking_url: str) -> str:
    """빈자리 맵을 사람이 읽을 메시지로 변환."""
    lines = ["🏥 [병원예약] 빈자리 발견!", ""]
    for date in sorted(open_slots):
        lines.append(f"📅 {date} — {open_slots[date]}자리")
    lines.append("")
    lines.append(f"👉 바로 예약: {booking_url}")
    return "\n".join(lines)


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
