# 네이버 예약 빈자리 감시 → 텔레그램 알림 설계

작성일: 2026-06-13

## 목적

네이버 예약으로 운영되는 병원 예약 페이지가 항상 꽉 차 있어, 자리가 비는
순간을 사람이 직접 잡기 어렵다. 빈자리가 생기면 즉시 텔레그램으로 알림을
보내 바로 예약할 수 있게 한다.

대상 페이지:
`https://booking.naver.com/booking/13/bizes/597072/items/5011045`
- businessId: `597072`
- bizItemId: `5011045`

## 핵심 결정 사항 (사용자 확정)

- **알림 방법**: 텔레그램 봇 (무료, 즉시 푸시)
- **실행 위치**: 클라우드 24시간 — Oracle Cloud 무료 티어 항상-켜짐 서버
- **감시 범위**: 오늘부터 향후 2달(약 60일)의 모든 영업일 (특정 날짜/시간대 제한 없음)
- **알림 정책**: "꽉참 → 빈자리" 로 **전환되는 순간에만** 알림 (스팸 방지)

> ⚠️ 갱신(2026-06-13): 아래 `schedule.daily` 기반 접근은 **실제 가용성을
> 반영하지 못함**이 확인되어 폐기됨. `daily.stock`/`bookingCount` 는 설정상
> 정원 템플릿이라, 예약이 꽉 차 있어도 자리가 남는 것처럼 나온다. 실제 구현은
> **`bizItem.availableStartDate`** 를 사용한다 — 마감이면 `null`, 자리가 나면
> "예약 가능한 가장 빠른 날짜" 문자열. 대부분 만석(`null`)이라, 이 값이
> 날짜로 나타나면(직전과 다른 날짜면 더 빠르든 늦든 무관) 무조건 알린다.
> 같은 날짜가 연속으로 떠 있으면 스팸 방지로 재알림하지 않는다.
> 쿼리: `query bizItem($input: BizItemParams) {
> bizItem(input: $input) { availableStartDate } }`, `input.projections` 는
> `"RESOURCE,MIN_MAX_PRICE,AVAILABLE_START_DATE"` (콤마 구분 문자열),
> ids 는 문자열. 라이브로 검증함(현재 null = 페이지가 실제로 만석).

## 데이터 소스 (초기 설계 — 폐기됨, 위 갱신 참고)

네이버 예약 GraphQL 엔드포인트로 날짜별 재고/예약 현황을 조회할 수 있음을
실제 호출로 확인했다.

- 엔드포인트: `POST https://booking.naver.com/graphql`
- operationName: `schedule`
- 필드 인자명은 `input`, 변수명은 `$scheduleParams` (타입 `ScheduleParams`)
- 필수 헤더: `Content-Type: application/json`,
  `Referer: https://booking.naver.com/booking/13/bizes/597072/items/5011045`
- businessId / bizItemId 는 **문자열**로 전달해야 함

쿼리:
```graphql
query schedule($scheduleParams: ScheduleParams) {
  schedule(input: $scheduleParams) {
    bizItemSchedule {
      daily { date }
    }
  }
}
```

> 중요: 네이버 스키마에서 `daily.date` 는 **JSON 스칼라**다. 하위 필드를
> 지정하면(`date { stock ... }`) HTTP 400(`Field "date" must not have a
> selection since type "JSON" has no subfields`)이 난다. 따라서 `date` 는
> leaf 로 선택하고, 응답으로 오는 JSON 스칼라 안에 날짜별 전체 객체
> (`stock`, `bookingCount`, `occupiedBookingCount`, `isSaleDay`,
> `isBusinessDay`, `isHoliday` 등)가 그대로 담겨 온다. (라이브 호출로 검증함)

variables 예시:
```json
{
  "scheduleParams": {
    "businessId": "597072",
    "bizItemId": "5011045",
    "startDateTime": "2026-06-13T00:00:00",
    "endDateTime": "2026-08-13T23:59:59"
  }
}
```

응답의 `bizItemSchedule.daily.date` 는 `"YYYY-MM-DD"` 키의 맵이며, 각 날짜
객체에 다음 필드가 들어있다 (실제 응답으로 확인):

| 필드 | 의미 |
|------|------|
| `date` | 날짜 |
| `stock` | 해당 날짜 총 정원 |
| `bookingCount` | 예약된 수 |
| `occupiedBookingCount` | 점유된 수 |
| `isSaleDay` | 판매(예약접수) 일 여부 |
| `isBusinessDay` | 영업일 여부 |
| `isHoliday` | 휴무일 여부 |

**빈자리 판정**:
`isSaleDay && isBusinessDay && (stock - bookingCount - occupiedBookingCount) > 0`
→ 남은 자리 수 = `stock - bookingCount - occupiedBookingCount`

> 참고: 위 daily 쿼리는 라이브 호출로 검증 완료. `date` 가 JSON 스칼라이므로
> 별도 셀렉션 확장 없이도 위 표의 모든 필드가 응답에 포함되어 온다.

## 아키텍처

```
[Oracle 무료 서버 / systemd]
   └─ main 루프 (60초 주기)
        1. naver_client.fetch(start, end)      → 날짜별 raw 데이터
        2. availability.compute(raw)           → {날짜: 남은자리수} (빈자리만)
        3. state_store 와 비교                  → 새로 열린 날짜 추출
        4. notifier.send(텔레그램)              → 사장님 폰 알림
        5. state_store.save(현재 상태)
```

### 구성 요소

각 단위는 하나의 명확한 책임을 가지며 독립적으로 테스트 가능하다.

1. **`naver_client`**
   - 책임: 네이버 GraphQL 호출 및 JSON 파싱
   - 입력: `(business_id, biz_item_id, start_date, end_date)`
   - 출력: 날짜별 원시 dict (stock/bookingCount 등)
   - 의존: `requests`, 네트워크
   - 실패: 타임아웃/HTTP오류/GraphQL errors → 예외 발생 (호출자가 처리)

2. **`availability`** (순수 함수)
   - 책임: 원시 응답 → `{ "YYYY-MM-DD": 남은자리수 }` (빈자리 있는 날만)
   - 입력: naver_client 출력
   - 출력: dict
   - 의존: 없음 (테스트 용이)

3. **`state_store`**
   - 책임: 직전 조회 결과를 로컬 파일(JSON)에 저장/로드
   - 입력/출력: `{ "YYYY-MM-DD": 남은자리수 }`
   - 의존: 파일시스템
   - 목적: "이번에 새로 열린 자리"만 계산

4. **`notifier`**
   - 책임: 텔레그램 Bot API로 메시지 전송
   - 입력: 메시지 문자열
   - 출력: 성공/실패
   - 의존: `requests`, 텔레그램 봇 토큰 + chat_id
   - 실패: 전송 실패 시 짧은 재시도 (예: 3회)

5. **`main`** (오케스트레이션)
   - 책임: 60초 루프, 단계 연결, 에러 격리
   - 의존: 위 1~4

### 새로 열린 자리 계산 로직

```
prev   = state_store.load()        # {날짜: 남은수}
cur    = availability.compute(...) # {날짜: 남은수}

# "꽉참 → 빈자리" 전환: 이전엔 없던(또는 0) 날짜가 이번에 빈자리로 등장
newly_open = { d: n for d, n in cur.items()
               if d not in prev }   # 직전에 빈자리 목록에 없던 날짜

if newly_open: notifier.send(...)
state_store.save(cur)
```

- 이미 빈자리였던 날(연속으로 빈자리)은 재알림하지 않음.
- 꽉 찼다가(목록에서 빠졌다가) 다시 열리면 다시 알림.

## 알림 메시지 형식 (예시)

```
🏥 [병원예약] 빈자리 발견!

📅 2026-06-20 (토) — 3자리
📅 2026-06-25 (목) — 1자리

👉 바로 예약: https://booking.naver.com/booking/13/bizes/597072/items/5011045
```

## 에러 처리

- 네이버 일시 오류/타임아웃: 로그 기록 후 다음 주기로 진행 (루프 죽지 않음).
- 텔레그램 전송 실패: 최대 3회 재시도.
- **연속 실패 감시**: 조회가 연속 10회(약 10분) 실패하면 텔레그램으로
  "⚠️ 감시 중단 위험" 경고 1회 발송 (복구되면 정상화 알림).

## 폴링 주기 / 예의

- 기본 60초 (설정값). 네이버 서버에 과부하 주지 않는 선.
- 요청 간 약간의 지터를 줄 수 있으나 우선 고정 60초로 시작.

## 기술 스택 / 배포

- 언어: Python 3
- 의존성: `requests` (최소화)
- 설정: 환경변수 / `.env` (봇 토큰, chat_id, business/bizItem id, 주기, 감시일수)
- 배포: Oracle Cloud 무료 티어 Ubuntu VM, `systemd` 서비스로 24시간 실행
  (재부팅 자동 재시작, 로그는 journald)

## 테스트 전략

- `availability.compute`: 다양한 stock/bookingCount/영업일 조합에 대한 단위 테스트.
- "새로 열린 자리" 계산: prev/cur 시나리오(신규 오픈, 연속 빈자리, 닫혔다 재오픈) 단위 테스트.
- `naver_client`: 저장된 실제 응답 샘플(fixture)로 파싱 테스트.
- `notifier`: 텔레그램 API 호출 모킹.

## 초기 설정 시 사용자 준비물

1. 텔레그램 봇 토큰 (@BotFather에서 생성) + 본인 chat_id
2. Oracle Cloud 무료 계정 (또는 항상 켜진 서버)

## 범위 밖 (YAGNI)

- 시간대(hourly) 단위 슬롯 세분화 — 우선 날짜 단위로 시작.
- 웹 대시보드/UI — 불필요.
- 다중 병원/다중 아이템 동시 감시 — 현재 1개 아이템만.
