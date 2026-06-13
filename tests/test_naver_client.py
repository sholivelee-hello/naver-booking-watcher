import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from watcher.naver_client import fetch_daily, NaverClientError

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "schedule_sample.json").read_text()
)


def _mock_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_fetch_daily_returns_date_map():
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(FIXTURE)) as post:
        result = fetch_daily("597072", "5011045", "2026-06-13", "2026-08-13")
    assert result["2026-06-13"]["stock"] == 48
    assert result["2026-06-15"]["bookingCount"] == 48
    sent = post.call_args.kwargs["json"]
    assert sent["variables"]["scheduleParams"]["businessId"] == "597072"
    assert sent["variables"]["scheduleParams"]["bizItemId"] == "5011045"
    assert sent["variables"]["scheduleParams"]["startDateTime"].startswith("2026-06-13")
    assert sent["variables"]["scheduleParams"]["endDateTime"].startswith("2026-08-13")


def test_fetch_daily_raises_on_graphql_errors():
    payload = {"errors": [{"message": "bad"}]}
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(payload)):
        with pytest.raises(NaverClientError):
            fetch_daily("597072", "5011045", "2026-06-13", "2026-08-13")


def test_fetch_daily_raises_on_unexpected_shape():
    payload = {"data": {"schedule": None}}
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(payload)):
        with pytest.raises(NaverClientError):
            fetch_daily("597072", "5011045", "2026-06-13", "2026-08-13")
