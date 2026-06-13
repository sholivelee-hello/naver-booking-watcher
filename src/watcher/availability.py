"""예약 가용성 전환 판정 — 순수 함수, I/O 없음."""


def detect_new_availability(prev, cur):
    """직전 availableStartDate(prev)와 이번 값(cur)을 비교해, 알릴 만한
    '새 가용성'이면 cur 을, 아니면 None 을 반환.

    - cur 이 None(여전히 마감) → None
    - cur 이 날짜이고 prev 와 다름(마감→오픈, 또는 더 빠른 날짜로 변경) → cur
    - cur 이 날짜이고 prev 와 같음(변화 없음) → None
    """
    if not cur:
        return None
    if cur == prev:
        return None
    return cur
