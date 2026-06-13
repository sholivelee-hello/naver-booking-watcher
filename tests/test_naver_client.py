from unittest.mock import patch, MagicMock

import pytest

from watcher.naver_client import fetch_available_start_date, NaverClientError


def _mock_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_fetch_returns_available_date():
    payload = {"data": {"bizItem": {"availableStartDate": "2026-06-20"}}}
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(payload)) as post:
        result = fetch_available_start_date("597072", "5011045")
    assert result == "2026-06-20"
    sent = post.call_args.kwargs["json"]
    assert sent["variables"]["input"]["businessId"] == "597072"
    assert sent["variables"]["input"]["bizItemId"] == "5011045"
    # projections 는 콤마 구분 문자열이어야 한다.
    assert "AVAILABLE_START_DATE" in sent["variables"]["input"]["projections"]


def test_fetch_returns_none_when_full():
    payload = {"data": {"bizItem": {"availableStartDate": None}}}
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(payload)):
        assert fetch_available_start_date("597072", "5011045") is None


def test_fetch_raises_on_graphql_errors():
    payload = {"errors": [{"message": "bad"}]}
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(payload)):
        with pytest.raises(NaverClientError):
            fetch_available_start_date("597072", "5011045")


def test_fetch_raises_on_unexpected_shape():
    payload = {"data": {"bizItem": None}}
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(payload)):
        with pytest.raises(NaverClientError):
            fetch_available_start_date("597072", "5011045")


def test_fetch_raises_on_null_json():
    # CDN/오류 페이지가 top-level JSON null 을 주면 data.get 이 AttributeError 로
    # 새어나가면 안 된다 → NaverClientError 로 정규화돼야 한다.
    with patch("watcher.naver_client.requests.post", return_value=_mock_response(None)):
        with pytest.raises(NaverClientError):
            fetch_available_start_date("597072", "5011045")


def test_fetch_raises_on_non_dict_json():
    # 배열 등 dict 가 아닌 JSON 도 마찬가지로 NaverClientError 여야 한다.
    with patch("watcher.naver_client.requests.post", return_value=_mock_response([1, 2])):
        with pytest.raises(NaverClientError):
            fetch_available_start_date("597072", "5011045")
