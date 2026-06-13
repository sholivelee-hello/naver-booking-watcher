from watcher.availability import detect_new_availability


def test_none_when_still_full():
    # 여전히 마감(cur None) → 알림 없음
    assert detect_new_availability(None, None) is None


def test_alerts_when_opens_from_full():
    # 마감(None) → 날짜 등장 → 알림
    assert detect_new_availability(None, "2026-06-20") == "2026-06-20"


def test_silent_when_date_unchanged():
    # 같은 날짜가 계속 가능 → 재알림 없음
    assert detect_new_availability("2026-06-20", "2026-06-20") is None


def test_alerts_when_earlier_date_appears():
    # 더 빠른 날짜로 바뀜 → 알림
    assert detect_new_availability("2026-06-20", "2026-06-15") == "2026-06-15"


def test_none_when_closes_again():
    # 가능했다가 다시 마감(None) → 알림 없음
    assert detect_new_availability("2026-06-20", None) is None
