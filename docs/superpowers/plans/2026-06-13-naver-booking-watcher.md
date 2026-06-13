# 네이버 예약 빈자리 감시 → 텔레그램 알림 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 네이버 예약 페이지를 60초마다 조회해 "꽉참→빈자리"로 전환되는 날짜를 감지하고 텔레그램으로 즉시 알림을 보낸다.

**Architecture:** 순수 함수(availability 판정)와 부수효과(naver_client, notifier, state_store)를 분리한 5개 모듈을 main 루프가 60초 주기로 오케스트레이션한다. 직전 상태를 파일에 저장해 신규 오픈만 알린다. Oracle Cloud 무료 VM에서 systemd 서비스로 24시간 실행.

**Tech Stack:** Python 3, `requests`, pytest, systemd

---

## File Structure

```
hospital/
├── src/
│   └── watcher/
│       ├── __init__.py
│       ├── config.py          # 환경변수 로딩 (토큰, id, 주기 등)
│       ├── naver_client.py    # 네이버 GraphQL 호출 + 파싱
│       ├── availability.py    # 순수 함수: raw → 빈자리 맵, 신규오픈 계산
│       ├── state_store.py     # 직전 상태 JSON 저장/로드
│       ├── notifier.py        # 텔레그램 전송
│       └── main.py            # 60초 루프 오케스트레이션
├── tests/
│   ├── fixtures/
│   │   └── schedule_sample.json   # 실제 네이버 응답 샘플
│   ├── test_availability.py
│   ├── test_state_store.py
│   ├── test_naver_client.py
│   └── test_notifier.py
├── deploy/
│   └── naver-watcher.service  # systemd 유닛
├── .env.example
├── requirements.txt
└── README.md                  # Oracle Cloud + 텔레그램 봇 설정 안내
```

Responsibilities:
- `config.py` — 모든 설정을 한 곳에서. 다른 모듈은 값만 받음.
- `naver_client.py` — 네트워크 I/O. 입력 (ids, 날짜범위) → 출력 raw daily dict.
- `availability.py` — I/O 없는 순수 함수. 테스트 핵심.
- `state_store.py` — 파일 I/O.
- `notifier.py` — 텔레그램 I/O.
- `main.py` — 위를 엮고 에러 격리/루프.

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `src/watcher/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`
- Create: `pytest.ini`

- [ ] **Step 1: requirements.txt 작성**

```
requests==2.32.3
pytest==8.3.3
```

- [ ] **Step 2: 패키지 디렉토리/초기화 파일 생성**

`src/watcher/__init__.py` (빈 파일):
```python
```

`tests/__init__.py` (빈 파일):
```python
```

- [ ] **Step 3: pytest.ini 작성 (src를 import 경로에 추가)**

`pytest.ini`:
```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 4: .env.example 작성**

`.env.example`:
```
# 텔레그램 봇 토큰 (@BotFather에서 발급)
TELEGRAM_BOT_TOKEN=123456:ABC-your-token-here
# 알림 받을 채팅 ID (본인 계정)
TELEGRAM_CHAT_ID=123456789
# 네이버 예약 대상
NAVER_BUSINESS_ID=597072
NAVER_BIZ_ITEM_ID=5011045
# 감시 설정
POLL_INTERVAL_SECONDS=60
WATCH_DAYS=60
# 상태 저장 파일 경로
STATE_FILE=state.json
```

- [ ] **Step 5: 의존성 설치 후 pytest 동작 확인**

Run: `pip install -r requirements.txt && python -m pytest -q`
Expected: `no tests ran` (에러 없이 종료)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src tests pytest.ini .env.example
git commit -m "chore: scaffold watcher project structure"
```

---

## Task 2: availability — 빈자리 판정 (순수 함수)

**Files:**
- Create: `src/watcher/availability.py`
- Test: `tests/test_availability.py`

빈자리 판정 규칙(spec): `isSaleDay && isBusinessDay && (stock - bookingCount - occupiedBookingCount) > 0`. 남은 자리 = `stock - bookingCount - occupiedBookingCount`.

- [ ] **Step 1: 실패하는 테스트 작성 — compute_open_slots**

`tests/test_availability.py`:
```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_availability.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'watcher.availability'`

- [ ] **Step 3: compute_open_slots 구현**

`src/watcher/availability.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_availability.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/watcher/availability.py tests/test_availability.py
git commit -m "feat: add open-slot computation"
```

---

## Task 3: availability — 신규 오픈 계산 (순수 함수)

**Files:**
- Modify: `src/watcher/availability.py`
- Test: `tests/test_availability.py`

신규 오픈(spec): 직전 빈자리 목록에 **없던** 날짜가 이번에 빈자리로 등장. 연속 빈자리는 재알림 안 함. 닫혔다 다시 열리면 재알림.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_availability.py` 끝에 추가:
```python
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
    # 이전 주기에 닫혀서 prev에 없음 → 다시 열리면 알림
    prev = {"2026-06-25": 2}
    cur = {"2026-06-20": 1}
    assert newly_opened(prev, cur) == {"2026-06-20": 1}


def test_newly_opened_empty_when_nothing_new():
    prev = {"2026-06-20": 3, "2026-06-21": 1}
    cur = {"2026-06-20": 2}
    assert newly_opened(prev, cur) == {}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_availability.py -k newly_opened -v`
Expected: FAIL — `ImportError: cannot import name 'newly_opened'`

- [ ] **Step 3: newly_opened 구현**

`src/watcher/availability.py` 끝에 추가:
```python
def newly_opened(prev: dict, cur: dict) -> dict:
    """직전 빈자리 맵(prev) 대비 이번에 새로 열린 날짜만 반환.

    prev에 없던 날짜가 cur에 빈자리로 등장하면 신규 오픈.
    """
    return {date: seats for date, seats in cur.items() if date not in prev}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_availability.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add src/watcher/availability.py tests/test_availability.py
git commit -m "feat: add newly-opened slot detection"
```

---

## Task 4: state_store — 직전 상태 저장/로드

**Files:**
- Create: `src/watcher/state_store.py`
- Test: `tests/test_state_store.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_state_store.py`:
```python
from watcher.state_store import load_state, save_state


def test_load_missing_file_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    assert load_state(str(path)) == {}


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    data = {"2026-06-20": 3, "2026-06-21": 1}
    save_state(str(path), data)
    assert load_state(str(path)) == data


def test_load_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json{{{")
    assert load_state(str(path)) == {}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_state_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'watcher.state_store'`

- [ ] **Step 3: state_store 구현**

`src/watcher/state_store.py`:
```python
"""직전 빈자리 상태를 JSON 파일로 저장/로드."""
import json
import os


def load_state(path: str) -> dict:
    """저장된 상태를 로드. 파일 없거나 손상되면 빈 dict."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: str, state: dict) -> None:
    """상태를 JSON으로 저장 (원자적 쓰기)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, path)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_state_store.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/watcher/state_store.py tests/test_state_store.py
git commit -m "feat: add state persistence"
```

---

## Task 5: naver_client — GraphQL 조회 + 파싱

**Files:**
- Create: `src/watcher/naver_client.py`
- Create: `tests/fixtures/schedule_sample.json`
- Test: `tests/test_naver_client.py`

검증된 호출(spec): `POST https://booking.naver.com/graphql`, operationName `schedule`, 필드 인자 `input`, 변수 `$scheduleParams: ScheduleParams`. ids는 문자열. Referer 헤더 필요. 응답 경로: `data.schedule.bizItemSchedule.daily.date` (날짜 맵).

- [ ] **Step 1: fixture 저장 (실제 응답 축약본)**

`tests/fixtures/schedule_sample.json`:
```json
{
  "data": {
    "schedule": {
      "bizItemSchedule": {
        "daily": {
          "date": {
            "2026-06-13": {"date": "2026-06-13", "isHoliday": false, "isBusinessDay": true, "isSaleDay": true, "stock": 48, "bookingCount": 0, "occupiedBookingCount": 0},
            "2026-06-14": {"date": "2026-06-14", "isHoliday": true, "isBusinessDay": false, "isSaleDay": true, "stock": 0, "bookingCount": 0, "occupiedBookingCount": 0},
            "2026-06-15": {"date": "2026-06-15", "isHoliday": false, "isBusinessDay": true, "isSaleDay": true, "stock": 48, "bookingCount": 48, "occupiedBookingCount": 0}
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: 실패하는 테스트 작성 (requests 모킹)**

`tests/test_naver_client.py`:
```python
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
    # ids가 문자열로 전송되는지 확인
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_naver_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'watcher.naver_client'`

- [ ] **Step 4: naver_client 구현**

`src/watcher/naver_client.py`:
```python
"""네이버 예약 GraphQL 클라이언트."""
import requests

GRAPHQL_URL = "https://booking.naver.com/graphql"

_QUERY = """
query schedule($scheduleParams: ScheduleParams) {
  schedule(input: $scheduleParams) {
    bizItemSchedule {
      daily {
        date {
          date
          isHoliday
          isBusinessDay
          isSaleDay
          stock
          bookingCount
          occupiedBookingCount
        }
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_naver_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: 실제 엔드포인트 연동 확인 (수동, 1회)**

Run:
```bash
python -c "from watcher.naver_client import fetch_daily; import json; print(json.dumps(list(fetch_daily('597072','5011045','2026-06-13','2026-06-20').items())[:1], ensure_ascii=False))"
```
(`src`가 PYTHONPATH에 없으면 `PYTHONPATH=src python -c ...`)
Expected: 첫 날짜의 stock/bookingCount가 출력됨 (네트워크 필요). 실패해도 다음 단계 진행 가능하나, 쿼리 셀렉션이 거부되면 여기서 즉시 드러남.

- [ ] **Step 7: Commit**

```bash
git add src/watcher/naver_client.py tests/test_naver_client.py tests/fixtures/schedule_sample.json
git commit -m "feat: add Naver booking GraphQL client"
```

---

## Task 6: notifier — 텔레그램 전송

**Files:**
- Create: `src/watcher/notifier.py`
- Test: `tests/test_notifier.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_notifier.py`:
```python
from unittest.mock import patch, MagicMock

from watcher.notifier import send_telegram, build_message


def _ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    return resp


def test_build_message_lists_dates_and_seats():
    msg = build_message(
        {"2026-06-20": 3, "2026-06-25": 1},
        "https://booking.naver.com/booking/13/bizes/597072/items/5011045",
    )
    assert "2026-06-20" in msg
    assert "3" in msg
    assert "2026-06-25" in msg
    assert "booking.naver.com" in msg


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
    with patch("watcher.notifier.requests.post", side_effect=requests.RequestException("boom")) as post:
        ok = send_telegram("TOKEN", "CHAT", "hello", retries=3)
    assert ok is False
    assert post.call_count == 3
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'watcher.notifier'`

- [ ] **Step 3: notifier 구현**

`src/watcher/notifier.py`:
```python
"""텔레그램 알림 전송."""
import requests


def build_message(open_slots: dict, booking_url: str) -> str:
    """빈자리 맵을 사람이 읽을 메시지로 변환."""
    lines = ["🏥 [병원예약] 빈자리 발견!", ""]
    for date in sorted(open_slots):
        lines.append(f"📅 {date} — {open_slots[date]}자리")
    lines.append("")
    lines.append(f"👉 바로 예약: {booking_url}")
    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str, retries: int = 3) -> bool:
    """텔레그램으로 메시지 전송. 실패 시 retries회 재시도. 성공=True."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    for _ in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            continue
    return False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/watcher/notifier.py tests/test_notifier.py
git commit -m "feat: add Telegram notifier"
```

---

## Task 7: config — 환경변수 로딩

**Files:**
- Create: `src/watcher/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_config.py`:
```python
import pytest

from watcher.config import load_config, ConfigError


def _env(**overrides):
    base = {
        "TELEGRAM_BOT_TOKEN": "tok",
        "TELEGRAM_CHAT_ID": "chat",
        "NAVER_BUSINESS_ID": "597072",
        "NAVER_BIZ_ITEM_ID": "5011045",
    }
    base.update(overrides)
    return base


def test_load_config_reads_values_and_defaults():
    cfg = load_config(_env())
    assert cfg.bot_token == "tok"
    assert cfg.business_id == "597072"
    assert cfg.poll_interval == 60        # default
    assert cfg.watch_days == 60           # default
    assert cfg.state_file == "state.json"  # default


def test_load_config_overrides_defaults():
    cfg = load_config(_env(POLL_INTERVAL_SECONDS="30", WATCH_DAYS="14"))
    assert cfg.poll_interval == 30
    assert cfg.watch_days == 14


def test_load_config_missing_required_raises():
    env = _env()
    del env["TELEGRAM_BOT_TOKEN"]
    with pytest.raises(ConfigError):
        load_config(env)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'watcher.config'`

- [ ] **Step 3: config 구현**

`src/watcher/config.py`:
```python
"""환경변수 기반 설정 로딩."""
from dataclasses import dataclass


class ConfigError(Exception):
    """필수 설정 누락."""


@dataclass
class Config:
    bot_token: str
    chat_id: str
    business_id: str
    biz_item_id: str
    poll_interval: int
    watch_days: int
    state_file: str

    @property
    def booking_url(self) -> str:
        return (
            f"https://booking.naver.com/booking/13/bizes/{self.business_id}"
            f"/items/{self.biz_item_id}"
        )


_REQUIRED = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "NAVER_BUSINESS_ID",
    "NAVER_BIZ_ITEM_ID",
]


def load_config(env: dict) -> Config:
    """env dict(보통 os.environ)에서 Config 생성. 필수값 없으면 ConfigError."""
    missing = [k for k in _REQUIRED if not env.get(k)]
    if missing:
        raise ConfigError(f"필수 환경변수 누락: {', '.join(missing)}")
    return Config(
        bot_token=env["TELEGRAM_BOT_TOKEN"],
        chat_id=env["TELEGRAM_CHAT_ID"],
        business_id=env["NAVER_BUSINESS_ID"],
        biz_item_id=env["NAVER_BIZ_ITEM_ID"],
        poll_interval=int(env.get("POLL_INTERVAL_SECONDS", "60")),
        watch_days=int(env.get("WATCH_DAYS", "60")),
        state_file=env.get("STATE_FILE", "state.json"),
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/watcher/config.py tests/test_config.py
git commit -m "feat: add config loading"
```

---

## Task 8: main — 한 주기 처리 함수 (run_once)

**Files:**
- Create: `src/watcher/main.py`
- Test: `tests/test_main.py`

루프 본체는 테스트하기 어렵지만, "한 주기"는 순수 조합 함수로 분리해 테스트한다. `run_once`는 fetch→compute→비교→알림→저장을 수행하고 신규 오픈 맵을 반환한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_main.py`:
```python
from unittest.mock import patch

from watcher.config import Config
from watcher.main import run_once


def _cfg(tmp_path):
    return Config(
        bot_token="tok", chat_id="chat",
        business_id="597072", biz_item_id="5011045",
        poll_interval=60, watch_days=60,
        state_file=str(tmp_path / "state.json"),
    )


def test_run_once_notifies_on_new_open(tmp_path):
    cfg = _cfg(tmp_path)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 45, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {"2026-06-20": 3}
    assert send.called


def test_run_once_no_notify_when_already_open(tmp_path):
    cfg = _cfg(tmp_path)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 45, "occupiedBookingCount": 0}}
    # 1회차: 알림 발생 + 상태 저장
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True):
        run_once(cfg, "2026-06-13", "2026-08-12")
    # 2회차: 여전히 빈자리 → 재알림 없음
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send2:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {}
    assert not send2.called


def test_run_once_skips_send_when_no_open(tmp_path):
    cfg = _cfg(tmp_path)
    raw = {"2026-06-20": {"isSaleDay": True, "isBusinessDay": True,
                          "stock": 48, "bookingCount": 48, "occupiedBookingCount": 0}}
    with patch("watcher.main.fetch_daily", return_value=raw), \
         patch("watcher.main.send_telegram", return_value=True) as send:
        new = run_once(cfg, "2026-06-13", "2026-08-12")
    assert new == {}
    assert not send.called
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'watcher.main'`

- [ ] **Step 3: run_once 구현 (루프 제외)**

`src/watcher/main.py`:
```python
"""감시 오케스트레이션."""
import logging

from watcher.availability import compute_open_slots, newly_opened
from watcher.naver_client import fetch_daily
from watcher.notifier import build_message, send_telegram
from watcher.state_store import load_state, save_state

log = logging.getLogger("watcher")


def run_once(cfg, start_date: str, end_date: str) -> dict:
    """한 주기 실행: 조회→판정→신규오픈 비교→알림→상태저장. 신규오픈 맵 반환."""
    raw = fetch_daily(cfg.business_id, cfg.biz_item_id, start_date, end_date)
    cur = compute_open_slots(raw)
    prev = load_state(cfg.state_file)
    new = newly_opened(prev, cur)
    if new:
        log.info("신규 빈자리 %d건: %s", len(new), new)
        msg = build_message(new, cfg.booking_url)
        send_telegram(cfg.bot_token, cfg.chat_id, msg)
    save_state(cfg.state_file, cur)
    return new
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/watcher/main.py tests/test_main.py
git commit -m "feat: add run_once orchestration"
```

---

## Task 9: main — 루프 + 연속 실패 경고 + 엔트리포인트

**Files:**
- Modify: `src/watcher/main.py`
- Test: `tests/test_main.py`

연속 실패 감시(spec): 조회가 연속 `FAIL_ALERT_THRESHOLD`(=10)회 실패하면 텔레그램 경고 1회. 복구되면 카운터 리셋.

- [ ] **Step 1: 실패하는 테스트 추가 — 날짜 범위 계산**

`tests/test_main.py` 끝에 추가:
```python
from datetime import date
from watcher.main import date_range


def test_date_range_spans_watch_days():
    start, end = date_range(date(2026, 6, 13), watch_days=60)
    assert start == "2026-06-13"
    assert end == "2026-08-12"   # 13 + 60일
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_main.py -k date_range -v`
Expected: FAIL — `ImportError: cannot import name 'date_range'`

- [ ] **Step 3: date_range + loop + main 구현**

`src/watcher/main.py` 상단 import에 추가:
```python
import os
import time
from datetime import date, timedelta
```

`src/watcher/main.py` 끝에 추가:
```python
FAIL_ALERT_THRESHOLD = 10


def date_range(today: date, watch_days: int):
    """오늘부터 watch_days일 후까지의 (start, end) "YYYY-MM-DD" 문자열."""
    start = today
    end = today + timedelta(days=watch_days)
    return start.isoformat(), end.isoformat()


def run_loop(cfg) -> None:
    """무한 루프: poll_interval마다 run_once. 에러 격리 + 연속실패 경고."""
    consecutive_failures = 0
    alerted = False
    while True:
        try:
            start, end = date_range(date.today(), cfg.watch_days)
            run_once(cfg, start, end)
            consecutive_failures = 0
            if alerted:
                send_telegram(cfg.bot_token, cfg.chat_id, "✅ 감시 정상 복구됨")
                alerted = False
        except Exception as e:  # 루프는 절대 죽지 않음
            consecutive_failures += 1
            log.warning("조회 실패 (%d회 연속): %s", consecutive_failures, e)
            if consecutive_failures >= FAIL_ALERT_THRESHOLD and not alerted:
                send_telegram(
                    cfg.bot_token, cfg.chat_id,
                    f"⚠️ 감시 중단 위험: {consecutive_failures}회 연속 조회 실패",
                )
                alerted = True
        time.sleep(cfg.poll_interval)


def main() -> None:
    from watcher.config import load_config
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config(os.environ)
    log.info("감시 시작: %s, %d일 범위, %d초 주기",
             cfg.booking_url, cfg.watch_days, cfg.poll_interval)
    run_loop(cfg)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 전체 테스트 통과 확인**

Run: `python -m pytest -v`
Expected: PASS (전체 통과)

- [ ] **Step 6: Commit**

```bash
git add src/watcher/main.py tests/test_main.py
git commit -m "feat: add watch loop with failure alerting and entrypoint"
```

---

## Task 10: 배포 파일 + README

**Files:**
- Create: `deploy/naver-watcher.service`
- Create: `README.md`

- [ ] **Step 1: systemd 유닛 작성**

`deploy/naver-watcher.service`:
```ini
[Unit]
Description=Naver Booking Availability Watcher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/naver-watcher
EnvironmentFile=/opt/naver-watcher/.env
ExecStart=/opt/naver-watcher/venv/bin/python -m watcher.main
Environment=PYTHONPATH=/opt/naver-watcher/src
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: README 작성 (텔레그램 봇 + Oracle 배포 안내)**

`README.md`:
```markdown
# 네이버 예약 빈자리 감시 → 텔레그램 알림

네이버 예약 페이지를 60초마다 확인해, 꽉 찼던 날짜에 빈자리가 생기면
텔레그램으로 즉시 알려줍니다.

## 1. 텔레그램 봇 만들기 (약 2분)

1. 텔레그램에서 `@BotFather` 검색 → 대화 시작
2. `/newbot` 입력 → 봇 이름과 사용자명 지정 → **토큰** 받기
   (`123456:ABC...` 형태)
3. 방금 만든 봇과 대화 시작( `/start` )
4. 본인 **chat_id** 확인: `@userinfobot` 에게 `/start` 보내면 숫자 ID를 알려줌

## 2. 로컬 테스트

```bash
pip install -r requirements.txt
cp .env.example .env   # .env 열어 토큰/chat_id 입력
PYTHONPATH=src python -m watcher.main
```

빈자리가 새로 생기면 텔레그램으로 알림이 옵니다. 종료는 Ctrl+C.

## 3. Oracle Cloud 무료 서버 배포

1. Oracle Cloud 무료 계정 생성 → Always Free Ubuntu VM 생성
2. SSH 접속 후:

```bash
sudo mkdir -p /opt/naver-watcher
sudo chown $USER /opt/naver-watcher
cd /opt/naver-watcher
# 코드 복사 (git clone 또는 scp)
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env   # 값 입력
```

3. systemd 등록:

```bash
sudo cp deploy/naver-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now naver-watcher
sudo systemctl status naver-watcher      # 동작 확인
journalctl -u naver-watcher -f           # 로그 실시간 보기
```

재부팅돼도 자동 시작되고, 오류가 나도 10초 후 재시작됩니다.

## 설정값 (.env)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| TELEGRAM_BOT_TOKEN | 봇 토큰 | (필수) |
| TELEGRAM_CHAT_ID | 알림 받을 chat id | (필수) |
| NAVER_BUSINESS_ID | 사업장 id | (필수) |
| NAVER_BIZ_ITEM_ID | 예약 항목 id | (필수) |
| POLL_INTERVAL_SECONDS | 확인 주기(초) | 60 |
| WATCH_DAYS | 감시 일수 | 60 |
| STATE_FILE | 상태 저장 파일 | state.json |
```

- [ ] **Step 3: Commit**

```bash
git add deploy/naver-watcher.service README.md
git commit -m "docs: add systemd unit and setup README"
```

---

## Self-Review (작성자 확인 완료)

**Spec coverage:**
- 데이터 소스/쿼리 → Task 5 ✓
- 빈자리 판정 → Task 2 ✓
- 신규오픈(스팸방지) → Task 3, 8 ✓
- 상태 저장 → Task 4 ✓
- 텔레그램 알림/메시지 형식 → Task 6 ✓
- 60초 루프 → Task 9 ✓
- 에러 처리 + 연속실패 경고 → Task 9 ✓
- 2달(60일) 범위 → Task 9 date_range (watch_days 기본 60), Task 7 ✓
- systemd 배포 + 설정 안내 → Task 10 ✓
- 테스트 전략(순수함수/파싱/모킹) → Task 2,3,4,5,6 ✓

**Type consistency:** `fetch_daily`, `compute_open_slots`, `newly_opened`,
`load_state`/`save_state`, `build_message`/`send_telegram`, `load_config`/`Config`,
`run_once`/`date_range`/`run_loop` — 정의와 호출부 시그니처 일치 확인.

**Placeholder scan:** 없음. 모든 코드 단계에 실제 코드 포함.
