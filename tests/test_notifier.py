from unittest.mock import patch, MagicMock

from watcher.notifier import send_telegram, build_message


def _ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    return resp


def test_build_message_includes_date_and_deeplink():
    msg = build_message(
        "2026-06-20",
        "https://booking.naver.com/booking/13/bizes/597072/items/5011045",
    )
    assert "2026-06-20" in msg
    assert "예약" in msg
    # 링크가 해당 날짜로 바로 가도록 startDate 가 붙어야 한다
    assert "startDate=2026-06-20" in msg


def test_send_telegram_posts_to_api():
    with patch("watcher.notifier.requests.post", return_value=_ok_response()) as post:
        ok = send_telegram("TOKEN", "CHAT", "hello")
    assert ok is True
    url = post.call_args.args[0]
    assert "TOKEN" in url and "sendMessage" in url
    assert post.call_args.kwargs["json"]["chat_id"] == "CHAT"
    assert post.call_args.kwargs["json"]["text"] == "hello"


def test_send_telegram_retries_then_fails():
    import requests
    with patch("watcher.notifier.requests.post", side_effect=requests.RequestException("boom")) as post:
        ok = send_telegram("TOKEN", "CHAT", "hello", retries=3)
    assert ok is False
    assert post.call_count == 3
