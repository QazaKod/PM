import os
import logging
from datetime import datetime
import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

import base64

# Load environment variables from .env
load_dotenv()

logger = logging.getLogger("admissions_api")

def get_bot_token() -> str:
    """
    Returns the Telegram Bot API token from environment (.env).
    Tokens must NEVER be hardcoded or committed into repository code.
    """
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


TELEGRAM_BOT_TOKEN = get_bot_token()
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "sdu_admissions_registration_bot").strip().lstrip("@")


def get_bot_username() -> str:
    """Returns the bot username for links."""
    return os.getenv("TELEGRAM_BOT_USERNAME", "sdu_admissions_registration_bot").strip().lstrip("@")


def is_telegram_configured() -> bool:
    """Checks whether TELEGRAM_BOT_TOKEN is set."""
    return bool(get_bot_token())


def get_telegram_deep_link(code: str) -> str:
    """Generates Telegram deep link with reset code."""
    username = get_bot_username()
    return f"https://t.me/{username}?start=reset_{code}"


def get_telegram_verification_link(code: str) -> str:
    """Generates Telegram deep link with account verification code."""
    username = get_bot_username()
    return f"https://t.me/{username}?start=verify_{code}"


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Sends a message to a specific Telegram chat_id."""
    token = get_bot_token()
    if not token:
        logger.info(f"ℹ️ Telegram bot token not configured. Message for {chat_id}: {text}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
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


def send_telegram_verification_code(chat_id: str, code: str, user_name: str = "Applicant") -> bool:
    """Sends formatted 6-digit registration verification code to user via Telegram."""
    message = (
        f"🏛️ <b>SDU Admissions Assistant</b>\n\n"
        f"Здравствуйте, <b>{user_name}</b>!\n"
        f"Ваш проверочный код для подтверждения регистрации на сайте:\n\n"
        f"👉 <code>{code}</code>\n\n"
        f"⏱ <i>Код действителен в течение 15 минут.</i>\n"
        f"Введите этот код на сайте для завершения регистрации."
    )
    logger.info(f"🔑 [Telegram Reg Code] Code for chat {chat_id}: {code}")
    return send_telegram_message(chat_id, message)


def process_telegram_update(update: dict, db: Session) -> dict:
    """
    Processes an incoming Telegram Webhook or Polling update.
    Handles /start reset_<CODE> and /start verify_<CODE> commands from users.
    """
    from app.models import PasswordResetToken, AccountVerificationToken, User

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
            .order_by(PasswordResetToken.id.desc())
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

    elif text.startswith("/start verify_") or text.startswith("/start reg_"):
        code = text.replace("/start verify_", "").replace("/start reg_", "").strip()
        token_entry = (
            db.query(AccountVerificationToken)
            .filter(
                AccountVerificationToken.code == code,
                AccountVerificationToken.is_used == False
            )
            .order_by(AccountVerificationToken.created_at.desc())
            .first()
        )

        if not token_entry or token_entry.expires_at < datetime.utcnow():
            reply_text = (
                "❌ <b>Код подтверждения недействителен или истек.</b>\n\n"
                "Пожалуйста, запросите новый код подтверждения на сайте SDU Admissions."
            )
            send_telegram_message(chat_id, reply_text)
            return {"status": "error", "message": "code invalid or expired"}

        user = token_entry.user
        if user:
            user.telegram_chat_id = chat_id
            if username:
                user.telegram_username = username
            db.commit()

        reply_text = (
            f"🏛️ <b>SDU Admissions Assistant</b>\n\n"
            f"Здравствуйте, <b>{user.full_name if user else first_name}</b>!\n"
            f"Ваш 6-значный проверочный код подтверждения регистрации:\n\n"
            f"👉 <code>{code}</code>\n\n"
            f"⏱ <i>Код действителен в течение 15 минут.</i>\n"
            f"Введите этот код в окне подтверждения на сайте для активации аккаунта."
        )
        send_telegram_message(chat_id, reply_text)
        return {"status": "ok", "action": "registration_code_delivered", "chat_id": chat_id, "code": code}

    elif text.startswith("/start"):
        reply_text = (
            f"🏛️ <b>SDU Admissions Assistant Bot</b>\n\n"
            f"Привет, <b>{first_name}</b>!\n"
            f"Я официальный бот приемной комиссии SDU University.\n\n"
            f"Здесь вы можете:\n"
            f"• Получать коды восстановления пароля\n"
            f"• Получать уведомления о статусе поступления\n\n"
            f"Для сброса пароля перейдите на сайт и выберите способ <i>«Via Telegram»</i>."
        )
        send_telegram_message(chat_id, reply_text)
        return {"status": "ok", "action": "welcome"}

    return {"status": "ok", "action": "unhandled_command"}


async def start_telegram_polling():
    """
    Background asynchronous polling worker for Telegram Bot updates.
    Listens for /start reset_<CODE> commands and delivers codes to users in Telegram.
    Runs continuously during server lifetime without blocking the event loop.
    """
    import asyncio

    token = get_bot_token()
    if not token:
        logger.info("ℹ️ Telegram bot token not configured. Background polling will not start.")
        return

    logger.info(f"🚀 Telegram Bot Poller starting for @{get_bot_username()}...")
    offset = 0
    base_url = f"https://api.telegram.org/bot{token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/getMe")
            if resp.status_code == 200 and resp.json().get("ok"):
                bot_user = resp.json().get("result", {})
                logger.info(f"✅ Telegram bot connected: @{bot_user.get('username')} ({bot_user.get('first_name')})")
            else:
                logger.error(f"❌ Telegram bot verification failed: {resp.text}")
                return
            # Delete any dangling webhook so getUpdates is allowed
            await client.post(f"{base_url}/deleteWebhook")
    except Exception as e:
        logger.warning(f"⚠️ Telegram bot initialization error: {e}")

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.get(f"{base_url}/getUpdates?offset={offset}&timeout=20")
                if res.status_code == 200:
                    data = res.json()
                    for update in data.get("result", []):
                        update_id = update.get("update_id")
                        offset = update_id + 1

                        from app.db_session import SessionLocal
                        db = SessionLocal()
                        try:
                            result = process_telegram_update(update, db)
                            logger.info(f"📩 Telegram update #{update_id} processed: {result}")
                        except Exception as err:
                            logger.error(f"⚠️ Error processing Telegram update #{update_id}: {err}")
                        finally:
                            db.close()
                elif res.status_code == 409:
                    # 409 Conflict: Another poller or process is listening
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            logger.info("🛑 Telegram polling background task stopped.")
            break
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            continue
        except Exception as e:
            logger.warning(f"⚠️ Telegram polling connection error: {e}")
            await asyncio.sleep(3)

