"""Gmail 앱 비밀번호(App Password)를 이용한 인증 메일 발송."""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

from config import (
    APP_BASE_URL,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    MAIL_FROM_NAME,
    TOKEN_TTL_HOURS,
    mail_configured,
)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


def build_verify_url(token: str) -> str:
    return f"{APP_BASE_URL}/?verify={quote(token, safe='')}"


def _build_message(to_email: str, verify_url: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "[관심종목 대시보드] 이메일 인증을 완료해 주세요"
    msg["From"] = formataddr((MAIL_FROM_NAME, GMAIL_USER))
    msg["To"] = to_email

    msg.set_content(
        "아래 주소를 브라우저에 붙여넣어 이메일 인증을 완료해 주세요.\n\n"
        f"{verify_url}\n\n"
        f"이 링크는 {TOKEN_TTL_HOURS}시간 동안만 유효합니다.\n"
        "본인이 요청한 것이 아니라면 이 메일을 무시하셔도 됩니다."
    )
    msg.add_alternative(
        f"""\
<html><body style="font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;
                   line-height:1.6;color:#1f2937">
  <h2 style="margin:0 0 12px">이메일 인증</h2>
  <p>관심종목 대시보드 가입을 완료하려면 아래 버튼을 눌러주세요.</p>
  <p style="margin:24px 0">
    <a href="{verify_url}"
       style="background:#2563eb;color:#fff;padding:12px 22px;border-radius:6px;
              text-decoration:none;display:inline-block">이메일 인증하기</a>
  </p>
  <p style="font-size:13px;color:#6b7280">
    버튼이 동작하지 않으면 아래 주소를 복사해 브라우저에 붙여넣으세요.<br>
    <span style="word-break:break-all">{verify_url}</span>
  </p>
  <p style="font-size:13px;color:#6b7280">
    링크는 {TOKEN_TTL_HOURS}시간 동안 유효하며, 본인이 요청하지 않았다면 무시하셔도 됩니다.
  </p>
</body></html>""",
        subtype="html",
    )
    return msg


def send_verification_mail(to_email: str, token: str) -> tuple[bool, str]:
    """(성공여부, 메시지). 설정이 없으면 발송하지 않고 False 를 돌려준다."""
    verify_url = build_verify_url(token)

    if not mail_configured():
        return False, "메일 발송 설정(GMAIL_USER / GMAIL_APP_PASSWORD)이 없습니다."

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(_build_message(to_email, verify_url))
        return True, f"{to_email} 로 인증 메일을 보냈습니다. 메일함을 확인해 주세요."
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail 인증 실패: 앱 비밀번호(16자리)와 계정을 확인해 주세요."
    except Exception as exc:  # 네트워크/SMTP 오류 전반
        return False, f"메일 발송 실패: {exc}"
