import os
import logging
from datetime import datetime
import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger("admissions_api")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "SDUAdmissionsAssistantBot").strip().lstrip("@")


def is_telegram_configured() -> bool:
    """Checks whether TELEGRAM_BOT_TOKEN is set."""
    return bool(TELEGRAM_BOT_TOKEN)


def get_bot_username() -> str:
    """Returns the bot username for links."""
    return TELEGRAM_BOT_USERNAME


def get_telegram_deep_link(code: str) -> str:
    """Generates Telegram deep link with reset code."""
    return f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=reset_{code}"


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Sends a message to a specific Telegram chat_id."""
    if not is_telegram_configured():
        logger.info(f"ℹ️ Telegram bot token not configured. Message for {chat_id}: {text}")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = httpx.post(url, json=payload, timeout=8.0)
        if response.status_code == 200:
            logger.info(f"✅ Telegram message successfully sent to chat {chat_id}")
            return True
        else:
            logger.error(f"❌ Telegram API returned error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram message: {e}")
        return False


def send_telegram_reset_code(chat_id: str, code: str, user_name: str = "Applicant") -> bool:
    """Sends formatted 6-digit password reset code to user via Telegram."""
    message = (
        f"🏛️ <b>SDU Admissions Assistant</b>\n\n"
        f"Здравствуйте, <b>{user_name}</b>!\n"
        f"Ваш проверочный код для сброса пароля на сайте:\n\n"
        f"👉 <code>{code}</code>\n\n"
        f"⏱ <i>Код действителен в течение 15 минут.</i>\n"
        f"Введите этот код на сайте для завершения смены пароля."
    )
    logger.info(f"🔑 [Telegram Reset] Code for chat {chat_id}: {code}")
    return send_telegram_message(chat_id, message)


def process_telegram_update(update: dict, db: Session) -> dict:
    """
    Processes an incoming Telegram Webhook update.
    Handles /start reset_<CODE> commands from users.
    """
    from app.models import PasswordResetToken, User

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return {"status": "ignored", "reason": "no message"}

    chat = msg.get("chat", {})
    from_user = msg.get("from") or {}
    chat_id = str(chat.get("id") or from_user.get("id"))
    username = chat.get("username") or from_user.get("username")
    first_name = from_user.get("first_name") or chat.get("first_name", "User")
    text = (msg.get("text") or "").strip()

    if text.startswith("/start reset_"):
        code = text.replace("/start reset_", "").strip()
        token_entry = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.code == code,
                PasswordResetToken.is_used == False
            )
            .order_by(PasswordResetToken.created_at.desc())
            .first()
        )

        if not token_entry or token_entry.expires_at < datetime.utcnow():
            reply_text = (
                "❌ <b>Код недействителен или истек.</b>\n\n"
                "Пожалуйста, запросите новый код сброса пароля на сайте SDU Admissions."
            )
            send_telegram_message(chat_id, reply_text)
            return {"status": "error", "message": "code invalid or expired"}

        # Code is valid! Link user's telegram account for future convenience
        user = token_entry.user
        if user:
            user.telegram_chat_id = chat_id
            if username:
                user.telegram_username = username
            db.commit()

        # Send the code back to the user in Telegram
        reply_text = (
            f"🏛️ <b>SDU Admissions Assistant</b>\n\n"
            f"Здравствуйте, <b>{user.full_name if user else first_name}</b>!\n"
            f"Ваш 6-значный проверочный код подтвержден:\n\n"
            f"👉 <code>{code}</code>\n\n"
            f"Введите этот код в окне сброса пароля на сайте для установки нового пароля."
        )
        send_telegram_message(chat_id, reply_text)
        return {"status": "ok", "action": "reset_code_delivered", "chat_id": chat_id, "code": code}

    elif text.startswith("/start"):
        reply_text = (
            f"🏛️ <b>SDU Admissions Assistant Bot</b>\n\n"
            f"Привет, <b>{first_name}</b>!\n"
            f"Я официальный бот приемной комиссии SDU University.\n\n"
            f"Здесь вы можете:\n"
            f"• Получать коды восстановления пароля\n"
            f"• Получать уведомления о поступлении\n\n"
            f"Для сброса пароля перейдите на сайт и нажмите <i>«Forgot password via Telegram»</i>."
        )
        send_telegram_message(chat_id, reply_text)
        return {"status": "ok", "action": "welcome"}

    return {"status": "ok", "action": "unhandled_command"}
