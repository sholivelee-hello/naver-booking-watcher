"""빈자리 판정 — 순수 함수, I/O 없음."""


def compute_open_slots(daily: dict) -> dict:
    """네이버 daily 맵을 받아 {날짜: 남은자리수} 반환 (빈자리 있는 날만).

    빈자리 판정: 판매일 && 영업일 && (stock - booked - occupied) > 0
    """
    open_slots = {}
    for date, info in daily.items():
        if not info.get("isSaleDay"):
            continue
        if not info.get("isBusinessDay"):
            continue
        stock = info.get("stock", 0) or 0
        booked = info.get("bookingCount", 0) or 0
        occupied = info.get("occupiedBookingCount", 0) or 0
        remaining = stock - booked - occupied
        if remaining > 0:
            open_slots[date] = remaining
    return open_slots


def newly_opened(prev: dict, cur: dict) -> dict:
    """직전 빈자리 맵(prev) 대비 이번에 새로 열린 날짜만 반환.

    prev에 없던 날짜가 cur에 빈자리로 등장하면 신규 오픈.
    """
    return {date: seats for date, seats in cur.items() if date not in prev}
