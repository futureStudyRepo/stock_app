"""SQLite 저장소 계층: 회원 / 이메일 인증 토큰 / 관심 종목."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

# DB 파일 위치. 기본은 코드 옆이지만, 도커에서는 볼륨을 붙인 경로를
# STOCK_APP_DB 로 넘겨 컨테이너를 지워도 회원 데이터가 남도록 한다.
DB_PATH = Path(os.getenv("STOCK_APP_DB") or Path(__file__).with_name("stock_app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    is_verified   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL,
    verified_at   TEXT
);

CREATE TABLE IF NOT EXISTS verification_tokens (
    token_hash TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT    NOT NULL,
    used_at    TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol     TEXT    NOT NULL,
    name       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    UNIQUE(user_id, symbol)
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


@contextmanager
def get_conn():
    """요청 단위 커넥션. Streamlit 이 여러 스레드에서 재실행하므로 매번 새로 연다."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    # 볼륨 경로(/data 등)가 아직 없을 수 있으므로 먼저 만든다.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------- 회원


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip(),)
        ).fetchone()


def create_user(email: str, password_hash: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email.strip(), password_hash, _iso(utcnow())),
        )
        return int(cur.lastrowid)


def update_password(user_id: int, password_hash: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )


def mark_verified(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET is_verified = 1, verified_at = ? WHERE id = ?",
            (_iso(utcnow()), user_id),
        )


# ---------------------------------------------------- 이메일 인증 토큰


def _hash_token(token: str) -> str:
    """토큰 원문은 저장하지 않고 해시만 보관한다(DB 유출 대비)."""
    return hashlib.sha256(token.encode()).hexdigest()


def save_token(user_id: int, token: str, ttl_hours: int) -> None:
    with get_conn() as conn:
        # 이전에 발급한 미사용 토큰은 무효화
        conn.execute(
            "DELETE FROM verification_tokens WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO verification_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_hash_token(token), user_id, _iso(utcnow() + timedelta(hours=ttl_hours))),
        )


def consume_token(token: str) -> tuple[bool, str]:
    """토큰 검증 + 사용 처리. (성공여부, 메시지) 반환."""
    token_hash = _hash_token(token)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT t.*, u.email, u.is_verified FROM verification_tokens t "
            "JOIN users u ON u.id = t.user_id WHERE t.token_hash = ?",
            (token_hash,),
        ).fetchone()

        if row is None:
            return False, "유효하지 않은 인증 링크입니다."
        if row["used_at"] is not None:
            return False, "이미 사용된 인증 링크입니다. 바로 로그인해 주세요."
        if _parse(row["expires_at"]) < utcnow():
            return False, "인증 링크가 만료되었습니다. 인증 메일을 다시 받아주세요."

        conn.execute(
            "UPDATE verification_tokens SET used_at = ? WHERE token_hash = ?",
            (_iso(utcnow()), token_hash),
        )
        conn.execute(
            "UPDATE users SET is_verified = 1, verified_at = ? WHERE id = ?",
            (_iso(utcnow()), row["user_id"]),
        )
        return True, f"{row['email']} 인증이 완료되었습니다. 로그인해 주세요."


# ------------------------------------------------------------ 관심 종목


def list_watchlist(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()


def add_watch(user_id: int, symbol: str, name: str) -> tuple[bool, str]:
    symbol, name = symbol.strip().upper(), name.strip()
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND symbol = ?", (user_id, symbol)
        ).fetchone()
        if exists:
            return False, f"{symbol} 은(는) 이미 관심 종목에 있습니다."
        conn.execute(
            "INSERT INTO watchlist (user_id, symbol, name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, symbol, name or symbol, _iso(utcnow())),
        )
        return True, f"{name or symbol} ({symbol}) 을(를) 추가했습니다."


def remove_watch(user_id: int, symbol: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?", (user_id, symbol)
        )
