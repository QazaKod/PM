import os
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("admissions_api")

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
EMAILS_FROM_EMAIL = os.getenv("EMAILS_FROM_EMAIL", "admission@sdu.edu.kz")
EMAILS_FROM_NAME = os.getenv("EMAILS_FROM_NAME", "SDU Admissions Assistant")


def is_smtp_configured() -> bool:
    """Check if SMTP credentials are provided in environment."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_password_reset_email(to_email: str, code: str, user_name: str = "Applicant") -> bool:
    """
    Sends a 6-digit password reset verification email.
    If SMTP credentials are not configured, logs the code clearly to the app logger.
    """
    subject = f"Your Password Reset Code: {code} — SDU Admissions Assistant"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f8fa; margin: 0; padding: 20px; }}
        .card {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .header h1 {{ color: #1289A7; margin: 0; font-size: 22px; }}
        .code-box {{ background: #e4f3f7; border: 2px dashed #1289A7; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0; }}
        .code {{ font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #0b1b2b; font-family: monospace; }}
        .footer {{ font-size: 12px; color: #8da0b3; text-align: center; margin-top: 24px; border-top: 1px solid #dfe7ed; padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>🏛️ SDU University</h1>
          <p style="color: #5c7085; margin-top: 4px;">Smart Admissions Assistant</p>
        </div>
        <p>Hello, <strong>{user_name}</strong>!</p>
        <p>We received a request to reset your password. Use the verification code below to set a new password:</p>
        <div class="code-box">
          <div class="code">{code}</div>
        </div>
        <p style="font-size: 13px; color: #5c7085;">This code is valid for <strong>15 minutes</strong>. If you did not request a password reset, you can safely ignore this email.</p>
        <div class="footer">
          SDU Admissions Office &bull; Abylai Khan str., 1/1, Kaskelen &bull; admission@sdu.edu.kz
        </div>
      </div>
    </body>
    </html>
    """

    # Always log to app logger for audit and immediate local testing
    logger.info(f"🔑 [Password Reset] Verification code for {to_email}: {code}")

    if not is_smtp_configured():
        logger.info(f"ℹ️ SMTP not configured. Code was logged to app.log for local testing.")
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{EMAILS_FROM_NAME} <{EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.set_content(f"Your SDU Admissions password reset code is: {code}\nValid for 15 minutes.")
        msg.add_alternative(html_content, subtype="html")

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

        logger.info(f"✅ Password reset email successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send password reset email via SMTP: {e}")
        return False
