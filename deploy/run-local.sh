#!/bin/bash
# .env 를 로드하고 감시기를 실행하는 래퍼 (launchd/수동 실행 공용).
# 프로젝트 루트를 기준으로 동작한다.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# .env 의 변수들을 환경에 export (주석/빈 줄 무시)
set -a
# shellcheck disable=SC1091
. ./.env
set +a

export PYTHONPATH=src

# launchd 는 PATH 가 빈약해 requests 없는 시스템 python 을 잡을 수 있으므로,
# requests 가 실제로 import 되는 인터프리터를 찾아 쓴다. 특정 버전 경로를
# 박아두면 그 빌드가 없을 때 조용히 죽으므로 후보를 순회해 검증한다.
# PYTHON_BIN 환경변수로 강제 지정할 수 있다.
find_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then echo "$PYTHON_BIN"; return 0; fi
  if [ -x "$PROJECT_DIR/venv/bin/python3" ]; then
    echo "$PROJECT_DIR/venv/bin/python3"; return 0
  fi
  local cand
  for cand in python3 \
      /opt/homebrew/bin/python3 \
      /usr/local/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
      /usr/bin/python3; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import requests' >/dev/null 2>&1; then
      command -v "$cand"; return 0
    fi
  done
  echo "오류: requests 가 설치된 python3 를 찾지 못했습니다. PYTHON_BIN 으로 지정하세요." >&2
  return 1
}

PYTHON_BIN="$(find_python)"
exec "$PYTHON_BIN" -m watcher.main
