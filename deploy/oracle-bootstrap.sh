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

    - cur 이 None(여전히 마감) → None
    - cur 이 날짜이고 prev 와 다름(마감→오픈, 또는 더 빠른 날짜로 변경) → cur
    - cur 이 날짜이고 prev 와 같음(변화 없음) → None
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
import requests


def build_message(available_date: str, booking_url: str) -> str:
    """예약 가능 날짜를 사람이 읽을 메시지로 변환."""
    return (
        "🏥 [병원예약] 예약 자리가 났어요!\n\n"
        f"📅 가장 빠른 예약 가능일: {available_date}\n\n"
        f"👉 지금 바로 예약: {booking_url}"
    )


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
    # 최초 실행(상태 파일 없음)에는 현재 값을 알림 없이 시드만 한다.
    # 이 분기가 없으면 첫 실행에서 이미 예약 가능한 상태일 때 곧바로 알림을
    # 보낸다. 다음 실행부터 마감→오픈 전환을 정상 감지한다.
    first_run = not os.path.exists(cfg.state_file)
    prev = load_state(cfg.state_file).get(_STATE_KEY)
    new = None if first_run else detect_new_availability(prev, cur)
    if new:
        log.info("예약 자리 발생: %s", new)
        msg = build_message(new, cfg.booking_url)
        send_telegram(cfg.bot_token, cfg.chat_id, msg)
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
