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
