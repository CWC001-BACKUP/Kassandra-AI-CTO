import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _is_configured() -> bool:
    settings = get_settings()
    return bool(settings.brevo_api_key and settings.from_email)


def _base_template(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#030712;font-family:Inter,Arial,sans-serif;color:#f8fafc;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#030712;padding:40px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:520px;background:#0c1222;border:1px solid #1e293b;border-radius:16px;overflow:hidden;">
        <tr><td style="padding:32px 28px;background:linear-gradient(135deg,#00D2FF22,#A020F022);">
          <h1 style="margin:0;font-size:22px;font-weight:700;color:#00D2FF;">Kassandra</h1>
        </td></tr>
        <tr><td style="padding:28px;">
          <h2 style="margin:0 0 12px;font-size:20px;color:#f8fafc;">{title}</h2>
          {body_html}
        </td></tr>
        <tr><td style="padding:20px 28px;border-top:1px solid #1e293b;color:#64748b;font-size:12px;">
          If you didn't request this, you can safely ignore this email.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _otp_block(code: str, minutes: int) -> str:
    return f"""
<p style="margin:0 0 20px;color:#94a3b8;line-height:1.6;">
  Use the code below to continue. It expires in <strong style="color:#e0f7ff;">{minutes} minutes</strong>.
</p>
<div style="text-align:center;margin:24px 0;">
  <span style="display:inline-block;padding:14px 28px;background:#111827;border:1px solid #00D2FF44;border-radius:12px;font-size:28px;font-weight:700;letter-spacing:8px;color:#00D2FF;">{code}</span>
</div>"""


async def _send_email(*, to_email: str, to_name: str, subject: str, html: str) -> bool:
    settings = get_settings()
    if not _is_configured():
        logger.warning("Brevo email not configured — skipping send to %s", to_email)
        return False

    payload: dict = {
        "sender": {"name": settings.from_name, "email": settings.from_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html,
    }
    if settings.reply_to_email:
        payload["replyTo"] = {"email": settings.reply_to_email}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            BREVO_API_URL,
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        logger.error(
            "Brevo API error %s: %s", response.status_code, response.text
        )
        raise RuntimeError("Failed to send email")

    return True


async def send_verification_email(
    to_email: str, to_name: str, code: str
) -> bool:
    settings = get_settings()
    html = _base_template(
        "Verify your email",
        _otp_block(code, settings.otp_expire_minutes)
        + f'<p style="margin:0;color:#94a3b8;">Welcome to Kassandra, {to_name or "there"}!</p>',
    )
    return await _send_email(
        to_email=to_email,
        to_name=to_name,
        subject="Your Kassandra verification code",
        html=html,
    )


async def send_password_reset_email(
    to_email: str, to_name: str, code: str
) -> bool:
    settings = get_settings()
    html = _base_template(
        "Reset your password",
        _otp_block(code, settings.otp_expire_minutes)
        + '<p style="margin:0;color:#94a3b8;">Enter this code on the reset password page to choose a new password.</p>',
    )
    return await _send_email(
        to_email=to_email,
        to_name=to_name,
        subject="Your Kassandra password reset code",
        html=html,
    )
