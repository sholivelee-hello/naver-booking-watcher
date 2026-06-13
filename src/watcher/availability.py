"""예약 가용성 전환 판정 — 순수 함수, I/O 없음."""


def detect_new_availability(prev, cur):
    """직전 값(prev)과 이번 값(cur)을 비교해, 알릴 만한 '새 가용성'이면
    cur 을, 아니면 None 을 반환.

    핵심: cur 은 "예약 가능한 시간이 있는가"의 신호다.
    - None  → 예약 가능한 시간이 하나도 없음(전석 마감)
    - 날짜  → 그 시점부터 예약 가능한 시간(자리)이 실제로 존재함

    이 페이지는 대부분 만석이라, 예약 가능한 시간이 생기는 순간이 곧 기회다.
    그래서 '예약 가능한 시간이 있으면(cur 이 None 이 아니면) 무조건' 알린다
    — 날짜가 더 빠르든 늦든 무관. 단, 직전과 완전히 같은 상태(동일 신호)가
    이어지는 경우만 스팸 방지로 재알림하지 않는다.

    - cur 이 None(예약 가능 시간 없음) → None
    - cur 에 자리가 있고 prev 와 다름(마감→오픈, 또는 가용 날짜 변경) → cur
    - cur 에 자리가 있고 prev 와 같음(변화 없음) → None
    """
    if not cur:
        return None
    if cur == prev:
        return None
    return cur
