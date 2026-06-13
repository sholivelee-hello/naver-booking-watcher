from watcher.availability import compute_open_slots


def _day(stock, booked, occupied=0, sale=True, biz=True):
    return {
        "stock": stock,
        "bookingCount": booked,
        "occupiedBookingCount": occupied,
        "isSaleDay": sale,
        "isBusinessDay": biz,
    }


def test_open_day_returns_remaining_seats():
    raw = {"2026-06-20": _day(stock=48, booked=45)}
    assert compute_open_slots(raw) == {"2026-06-20": 3}


def test_full_day_excluded():
    raw = {"2026-06-20": _day(stock=48, booked=48)}
    assert compute_open_slots(raw) == {}


def test_occupied_counts_against_capacity():
    raw = {"2026-06-20": _day(stock=10, booked=7, occupied=3)}
    assert compute_open_slots(raw) == {}


def test_non_business_day_excluded():
    raw = {"2026-06-21": _day(stock=10, booked=0, biz=False)}
    assert compute_open_slots(raw) == {}


def test_non_sale_day_excluded():
    raw = {"2026-06-21": _day(stock=10, booked=0, sale=False)}
    assert compute_open_slots(raw) == {}


def test_missing_fields_treated_as_full():
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True}}
    assert compute_open_slots(raw) == {}


from watcher.availability import newly_opened


def test_newly_opened_detects_brand_new_date():
    prev = {}
    cur = {"2026-06-20": 3}
    assert newly_opened(prev, cur) == {"2026-06-20": 3}


def test_newly_opened_ignores_still_open_date():
    prev = {"2026-06-20": 3}
    cur = {"2026-06-20": 1}
    assert newly_opened(prev, cur) == {}


def test_newly_opened_realerts_after_reclosed():
    prev = {"2026-06-25": 2}
    cur = {"2026-06-20": 1}
    assert newly_opened(prev, cur) == {"2026-06-20": 1}


def test_newly_opened_empty_when_nothing_new():
    prev = {"2026-06-20": 3, "2026-06-21": 1}
    cur = {"2026-06-20": 2}
    assert newly_opened(prev, cur) == {}
