# 네이버 예약 빈자리 감시 → 텔레그램 알림

네이버 예약 페이지를 60초마다 확인해, 예약이 꽉 차 있던 항목에 자리가
생기면(= 예약 가능한 날짜가 나타나면) 텔레그램으로 즉시 알려줍니다.

> 감지 신호: 네이버 `bizItem.availableStartDate`. 자리가 전부 차 있으면
> `null`, 자리가 나면 "예약 가능한 가장 빠른 날짜"가 채워진다. 이 값이
> 마감(`null`)에서 날짜로 바뀌는 순간(또는 더 빠른 날짜로 바뀔 때) 알린다.

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

예약 가능한 자리가 새로 생기면 텔레그램으로 알림이 옵니다. 종료는 Ctrl+C.

## 2-0. GitHub Actions로 24시간 실행 (서버·카드 불필요, 무료, ~1분 간격)

**공개(public) 저장소**에 올리면 GitHub Actions가 무제한 무료로 돌아간다.
워크플로우 한 회차가 ~50분 동안 60초 간격으로 확인하고, `concurrency` 직렬화로
대기 중인 다음 회차가 현재 회차 종료(또는 크래시) 즉시 이어받는다.
공백은 회차 전환 시 러너 부팅 시간(~1분)뿐이라 **사실상 24시간 연속 감시**가
된다. 컴퓨터가 꺼져 있어도 동작.

1. 저장소를 본인 **개인** GitHub 계정에 push (private 권장).
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   에 다음 두 개 등록:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. `.github/workflows/watch.yml` 가 포함돼 있으면 자동으로 스케줄 실행된다.
   **Actions** 탭에서 수동 실행(Run workflow)도 가능.

동작 방식:
- 각 회차는 `python -m watcher.main --minutes 50` 로 50분간 60초 주기로 확인.
- cron(`*/5`)은 대기 회차 1개를 항상 채워 두는 용도 — `concurrency` 직렬화로
  동시 실행은 막고(중복 알림 방지), 현재 회차가 끝나면 대기 회차가 바로 이어받는다.
- 상태는 `state/state.json` 에 저장되며, 값이 바뀌면 워크플로우가 저장소에
  자동 커밋(rebase+재시도, 충돌 시 최신 상태 우선)해 다음 회차가 전환을
  감지할 수 있게 한다. 푸시가 실패해도 알림은 이미 발송됐으므로 누락되지 않는다.

> 공개 저장소라야 무제한 무료다. 코드엔 비밀정보가 없고, 텔레그램 토큰은
> 저장소가 아니라 Actions 시크릿에 저장된다.

## 2-1. Mac에서 24시간 백그라운드 실행 (launchd)

로그아웃·재부팅에도 살아남고, 죽으면 자동 재시작된다.

```bash
# 1) .env 작성 후, 실행 래퍼에 권한 부여
chmod +x deploy/run-local.sh

# 2) LaunchAgent 등록 (plist 안의 경로를 본인 환경에 맞게 수정)
cp deploy/com.hospital.naver-watcher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hospital.naver-watcher.plist

# 3) 상태 / 로그 확인
launchctl list | grep naver-watcher      # 가운데 값이 0이면 정상
tail -f logs/watcher.log

# 중지하려면
launchctl unload ~/Library/LaunchAgents/com.hospital.naver-watcher.plist
```

> 주의: launchd 는 PATH 가 달라 `requests` 없는 시스템 python 을 잡을 수 있다.
> `deploy/run-local.sh` 가 requests 설치된 인터프리터를 명시한다
> (`PYTHON_BIN` 환경변수로 override 가능).

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
| STATE_FILE | 상태 저장 파일 | state.json |
