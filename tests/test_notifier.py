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
    with patch("watcher.notifier.requests.post", side_effect=requests.RequestException("boom")) as post, \
         patch("watcher.notifier.time.sleep") as sleep:
        ok = send_telegram("TOKEN", "CHAT", "hello", retries=3)
    assert ok is False
    assert post.call_count == 3
    # 시도 사이에만 대기 (마지막 시도 뒤에는 대기 안 함) → retries-1회
    assert sleep.call_count == 2


def _err_response(status, headers=None):
    import requests
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def test_send_telegram_uses_exponential_backoff():
    import requests
    with patch("watcher.notifier.requests.post", side_effect=requests.RequestException("boom")), \
         patch("watcher.notifier.time.sleep") as sleep:
        send_telegram("T", "C", "x", retries=3, backoff=2.0)
    # 고정이 아니라 지수: 2, 4
    assert [c.args[0] for c in sleep.call_args_list] == [2.0, 4.0]


def test_send_telegram_honors_retry_after_on_429():
    with patch("watcher.notifier.requests.post", return_value=_err_response(429, {"Retry-After": "30"})), \
         patch("watcher.notifier.time.sleep") as sleep:
        ok = send_telegram("T", "C", "x", retries=2, backoff=2.0)
    assert ok is False
    # 429 면 백오프 대신 Retry-After 를 존중해야 한다
    assert sleep.call_args_list[0].args[0] == 30.0


def test_send_telegram_no_retry_on_permanent_4xx():
    with patch("watcher.notifier.requests.post", return_value=_err_response(400)) as post, \
         patch("watcher.notifier.time.sleep") as sleep:
        ok = send_telegram("T", "C", "x", retries=3)
    assert ok is False
    # 400(예: chat not found)은 재시도해도 소용없으니 즉시 중단
    assert post.call_count == 1
    assert not sleep.called
