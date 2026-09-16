"""환경 설정 로딩 (.env 또는 OS 환경변수)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# Gmail 발신 계정 + 앱 비밀번호(16자리). 2단계 인증 계정에서만 발급된다.
GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Stock Watchlist").strip()

# 인증 링크에 사용할 앱 주소 (배포 시 실제 도메인으로 교체)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/")

TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "24"))

# 메일 발송이 불가능한 개발 환경에서 인증 링크를 화면에 직접 표시할지 여부
DEV_SHOW_LINK = _bool(os.getenv("DEV_SHOW_LINK"), default=True)


def mail_configured() -> bool:
    return bool(GMAIL_USER and GMAIL_APP_PASSWORD)
