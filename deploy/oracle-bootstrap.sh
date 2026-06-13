#!/usr/bin/env bash
#
# Oracle Cloud (Ubuntu) 1줄 설치 스크립트 — 네이버 예약 빈자리 감시기.
# GitHub 불필요: 코드가 이 스크립트 안에 모두 들어있다.
#
# 사용법 (서버 SSH 접속 후, 본인 값으로 채워서 실행):
#   TELEGRAM_BOT_TOKEN='123:abc' TELEGRAM_CHAT_ID='123456' \
#   bash oracle-bootstrap.sh
#
# NAVER_BUSINESS_ID / NAVER_BIZ_ITEM_ID 는 기본값(597072 / 5011045)을 쓰며
# 필요시 같은 방식으로 덮어쓸 수 있다.
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/naver-watcher}"
NAVER_BUSINESS_ID="${NAVER_BUSINESS_ID:-597072}"
NAVER_BIZ_ITEM_ID="${NAVER_BIZ_ITEM_ID:-5011045}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-60}"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "오류: TELEGRAM_BOT_TOKEN 과 TELEGRAM_CHAT_ID 를 지정해야 합니다." >&2
  echo "예: TELEGRAM_BOT_TOKEN='...' TELEGRAM_CHAT_ID='...' bash oracle-bootstrap.sh" >&2
  exit 1
fi

echo ">>> 1/6 패키지 설치 (python3-venv)"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip

echo ">>> 2/6 앱 디렉토리 생성: $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo chown "$USER" "$APP_DIR"
mkdir -p "$APP_DIR/src/watcher"
echo ">>> 3/6 소스 파일 작성"
cat > "$APP_DIR/requirements.txt" <<'WATCHER_EOF_4460'
requests==2.32.3
pytest==8.3.3
WATCHER_EOF_4460

cat > "$APP_DIR/src/watcher/__init__.py" <<'WATCHER_EOF_7699'
WATCHER_EOF_7699

cat > "$APP_DIR/src/watcher/config.py" <<'WATCHER_EOF_365'
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
        state_file=env.get("STATE_FILE", "state.json"),
    )
WATCHER_EOF_365

cat > "$APP_DIR/src/watcher/availability.py" <<'WATCHER_EOF_3600'
"""예약 가용성 전환 판정 — 순수 함수, I/O 없음."""


def detect_new_availability(prev, cur):
    """직전 availableStartDate(prev)와 이번 값(cur)을 비교해, 알릴 만한
    '새 가용성'이면 cur 을, 아니면 None 을 반환.

    핵심: cur 은 "예약 가능한 시간이 있는가"의 신호다.
    None 이면 예약 가능한 시간이 하나도 없음(마감), 날짜면 그 시점부터
    예약 가능한 시간(자리)이 실제로 존재한다. 대부분 만석이라 자리가 생기는
    순간이 곧 기회이므로, '예약 가능한 시간이 있으면(None 이 아니면) 무조건'
    알린다(날짜가 빠르든 늦든 무관). 직전과 동일한 상태만 스팸 방지로 건너뛴다.

    - cur 이 None(예약 가능 시간 없음) → None
    - cur 에 자리가 있고 prev 와 다름(마감→오픈, 또는 가용 날짜 변경) → cur
    - cur 에 자리가 있고 prev 와 같음(변화 없음) → None
    """
    if not cur:
        return None
    if cur == prev:
        return None
    return cur
WATCHER_EOF_3600

cat > "$APP_DIR/src/watcher/naver_client.py" <<'WATCHER_EOF_5133'
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
WATCHER_EOF_5133

cat > "$APP_DIR/src/watcher/notifier.py" <<'WATCHER_EOF_4906'
"""텔레그램 알림 전송."""
import logging
import time

import requests

log = logging.getLogger("watcher.notifier")


def build_message(available_date: str, booking_url: str) -> str:
    """예약 가능 날짜를 사람이 읽을 메시지로 변환.

    링크는 해당 날짜로 바로 가도록 startDate 를 붙인다 → 누르면 그날 비어있는
    시간이 바로 보인다.
    """
    sep = "&" if "?" in booking_url else "?"
    dated_link = f"{booking_url}{sep}startDate={available_date}"
    return (
        "🏥 [병원예약] 예약 자리가 났어요!\n\n"
        f"📅 예약 가능일: {available_date}\n"
        "👇 누르면 그날 비어있는 시간이 바로 보여요\n"
        f"{dated_link}"
    )


def send_telegram(token: str, chat_id: str, text: str,
                  retries: int = 3, backoff: float = 2.0) -> bool:
    """텔레그램으로 메시지 전송. 실패 시 retries회 재시도(사이에 backoff초 대기). 성공=True."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff)
    log.warning("텔레그램 전송 %d회 모두 실패: %s", retries, last_exc)
    return False
WATCHER_EOF_4906

cat > "$APP_DIR/src/watcher/state_store.py" <<'WATCHER_EOF_1572'
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
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, path)
WATCHER_EOF_1572

cat > "$APP_DIR/src/watcher/main.py" <<'WATCHER_EOF_281'
"""감시 오케스트레이션."""
import logging
import os
import time

from watcher.availability import detect_new_availability
from watcher.naver_client import fetch_available_start_date
from watcher.notifier import build_message, send_telegram
from watcher.state_store import load_state, save_state

log = logging.getLogger("watcher")

FAIL_ALERT_THRESHOLD = 10
_STATE_KEY = "availableStartDate"


def run_once(cfg):
    """한 주기 실행: 조회→전환 판정→알림→상태저장. 새로 난 날짜(또는 None) 반환."""
    cur = fetch_available_start_date(cfg.business_id, cfg.biz_item_id)
    state = load_state(cfg.state_file)
    # 최초 실행(상태 없음 또는 손상)에는 현재 값을 알림 없이 시드만 한다.
    # 파일 존재 여부가 아니라 상태 키 존재로 판정한다 — 파일이 깨져
    # load_state 가 {} 를 돌려줄 때도 오탐 없이 다시 시드된다.
    first_run = _STATE_KEY not in state
    prev = state.get(_STATE_KEY)
    new = None if first_run else detect_new_availability(prev, cur)
    if new:
        log.info("예약 자리 발생: %s", new)
        msg = build_message(new, cfg.booking_url)
        if not send_telegram(cfg.bot_token, cfg.chat_id, msg):
            # 전송 실패 시 상태 미갱신 → 다음 주기에 같은 전환을 재시도.
            log.warning("알림 전송 실패 — 상태 미갱신, 다음 주기 재시도: %s", new)
            return new
    save_state(cfg.state_file, {_STATE_KEY: cur})
    return new


def run_loop(cfg) -> None:
    """무한 루프: poll_interval마다 run_once. 에러 격리 + 연속실패 경고."""
    consecutive_failures = 0
    alerted = False
    while True:
        try:
            run_once(cfg)
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
    log.info("감시 시작: %s, %d초 주기", cfg.booking_url, cfg.poll_interval)
    run_loop(cfg)


if __name__ == "__main__":
    main()
WATCHER_EOF_281

echo ">>> 4/6 가상환경 + 의존성 설치"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo ">>> 5/6 .env 작성"
cat > "$APP_DIR/.env" <<ENV_EOF
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID
NAVER_BUSINESS_ID=$NAVER_BUSINESS_ID
NAVER_BIZ_ITEM_ID=$NAVER_BIZ_ITEM_ID
POLL_INTERVAL_SECONDS=$POLL_INTERVAL_SECONDS
STATE_FILE=$APP_DIR/state.json
ENV_EOF
chmod 600 "$APP_DIR/.env"

echo ">>> 6/6 systemd 서비스 등록"
sudo tee /etc/systemd/system/naver-watcher.service >/dev/null <<UNIT_EOF
[Unit]
Description=Naver Booking Availability Watcher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=PYTHONPATH=$APP_DIR/src
ExecStart=$APP_DIR/venv/bin/python -m watcher.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT_EOF

sudo systemctl daemon-reload
sudo systemctl enable --now naver-watcher

sleep 3
echo ""
echo "===== 설치 완료 ====="
sudo systemctl status naver-watcher --no-pager -l | head -12 || true
echo ""
echo "로그 실시간 보기:  journalctl -u naver-watcher -f"
echo "중지:             sudo systemctl stop naver-watcher"
echo "시작:             sudo systemctl start naver-watcher"
