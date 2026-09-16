"""비밀번호 해싱 / 인증 토큰 / 회원가입·로그인 유스케이스."""
import re
import secrets

import bcrypt

import db
from config import TOKEN_TTL_HOURS

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
MIN_PASSWORD_LEN = 8


# ------------------------------------------------------------ 비밀번호


def hash_password(plain: str) -> str:
    """bcrypt 해시(솔트 포함) 문자열을 돌려준다. 평문은 절대 저장하지 않는다."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def validate_signup(email: str, password: str, password2: str) -> str | None:
    """문제가 있으면 오류 메시지를, 없으면 None 을 돌려준다."""
    if not EMAIL_RE.match(email.strip()):
        return "이메일 형식이 올바르지 않습니다."
    if len(password) < MIN_PASSWORD_LEN:
        return f"비밀번호는 {MIN_PASSWORD_LEN}자 이상이어야 합니다."
    if password != password2:
        return "비밀번호가 서로 일치하지 않습니다."
    return None


# ------------------------------------------------------------ 토큰


def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.save_token(user_id, token, TOKEN_TTL_HOURS)
    return token


# ------------------------------------------------------------ 유스케이스


def register(email: str, password: str) -> tuple[int, str]:
    """신규 가입 또는 미인증 계정 재가입. (user_id, token) 반환."""
    email = email.strip()
    existing = db.get_user_by_email(email)

    if existing is not None:
        if existing["is_verified"]:
            raise ValueError("이미 가입된 이메일입니다. 로그인해 주세요.")
        # 아직 인증 전이라면 비밀번호를 갱신하고 토큰을 새로 발급한다.
        user_id = int(existing["id"])
        db.update_password(user_id, hash_password(password))
    else:
        user_id = db.create_user(email, hash_password(password))

    return user_id, issue_token(user_id)


def login(email: str, password: str) -> dict:
    user = db.get_user_by_email(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise ValueError("이메일 또는 비밀번호가 올바르지 않습니다.")
    if not user["is_verified"]:
        raise ValueError("이메일 인증이 완료되지 않았습니다. 받은 인증 메일을 확인해 주세요.")
    return {"id": int(user["id"]), "email": user["email"]}
