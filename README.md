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
