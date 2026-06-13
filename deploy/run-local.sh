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
# launchd 는 PATH 가 달라 requests 없는 시스템 python 을 잡을 수 있으므로
# requests 가 설치된 인터프리터를 명시한다. (PYTHON_BIN 으로 override 가능)
PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}"
exec "$PYTHON_BIN" -m watcher.main
