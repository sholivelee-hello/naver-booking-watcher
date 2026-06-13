"""네이버 예약 GraphQL 클라이언트."""
import requests

GRAPHQL_URL = "https://booking.naver.com/graphql"

# bizItem.availableStartDate 가 실제 "예약 가능한 가장 빠른 날짜"다.
# 자리가 전부 차 있으면 null, 자리가 나면 날짜 문자열("YYYY-MM-DD")이 된다.
# (schedule.daily 의 stock 은 설정상 정원 템플릿이라 실제 가용성과 무관하다.)
_QUERY = """
query bizItem($input: BizItemParams) {
  bizItem(input: $input) {
    bizItemId
    name
    availableStartDate
    isClosedBooking
  }
}
"""

_PROJECTIONS = "RESOURCE,MIN_MAX_PRICE,AVAILABLE_START_DATE"


class NaverClientError(Exception):
    """네이버 조회/파싱 실패."""


def fetch_available_start_date(business_id: str, biz_item_id: str,
                               timeout: int = 15):
    """예약 가능한 가장 빠른 날짜를 반환. 자리가 없으면 None.

    반환: "YYYY-MM-DD" 문자열 또는 None.
    """
    referer = (
        f"https://booking.naver.com/booking/13/bizes/{business_id}"
        f"/items/{biz_item_id}"
    )
    payload = {
        "operationName": "bizItem",
        "variables": {
            "input": {
                "businessId": str(business_id),
                "bizItemId": str(biz_item_id),
                "lang": "ko",
                "projections": _PROJECTIONS,
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
        return data["data"]["bizItem"]["availableStartDate"]
    except (TypeError, KeyError) as e:
        raise NaverClientError(f"예상치 못한 응답 구조: {e}") from e
