"""네이버 예약 GraphQL 클라이언트."""
import requests

GRAPHQL_URL = "https://booking.naver.com/graphql"

_QUERY = """
query schedule($scheduleParams: ScheduleParams) {
  schedule(input: $scheduleParams) {
    bizItemSchedule {
      daily {
        date
      }
    }
  }
}
"""


class NaverClientError(Exception):
    """네이버 조회/파싱 실패."""


def fetch_daily(business_id: str, biz_item_id: str,
                start_date: str, end_date: str, timeout: int = 15) -> dict:
    """날짜별 raw 일정 맵 반환. {날짜: {stock, bookingCount, ...}}.

    start_date / end_date 는 "YYYY-MM-DD".
    """
    referer = (
        f"https://booking.naver.com/booking/13/bizes/{business_id}"
        f"/items/{biz_item_id}"
    )
    payload = {
        "operationName": "schedule",
        "variables": {
            "scheduleParams": {
                "businessId": str(business_id),
                "bizItemId": str(biz_item_id),
                "startDateTime": f"{start_date}T00:00:00",
                "endDateTime": f"{end_date}T23:59:59",
            }
        },
        "query": _QUERY,
    }
    headers = {
        "Content-Type": "application/json",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0",
    }
    try:
        resp = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise NaverClientError(f"요청 실패: {e}") from e

    if data.get("errors"):
        raise NaverClientError(f"GraphQL 오류: {data['errors']}")

    try:
        return data["data"]["schedule"]["bizItemSchedule"]["daily"]["date"]
    except (TypeError, KeyError) as e:
        raise NaverClientError(f"예상치 못한 응답 구조: {e}") from e
