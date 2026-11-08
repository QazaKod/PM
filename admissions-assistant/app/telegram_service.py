import os
import re
import logging
from datetime import datetime
from typing import Optional
import httpx
from dotenv import load_dotenv
from sqlalchemy import or_
from sqlalchemy.orm import Session

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


def get_telegram_deep_link(token_or_code: str) -> str:
    """Generates Telegram deep link with reset session token or code."""
    username = get_bot_username()
    return f"https://t.me/{username}?start=reset_{token_or_code}"


def get_telegram_verification_link(token_or_code: str) -> str:
    """Generates Telegram deep link with account verification session token or code."""
    username = get_bot_username()
    return f"https://t.me/{username}?start=verify_{token_or_code}"



def phones_match(phone1: Optional[str], phone2: Optional[str]) -> bool:
    """
    Compares two phone numbers by normalizing Kazakhstan 87... -> 77...
    and comparing the last 10 subscriber digits.
    """
    if not phone1 or not phone2:
        return False
    d1 = re.sub(r"\D", "", str(phone1))
    d2 = re.sub(r"\D", "", str(phone2))
    if len(d1) == 11 and d1.startswith("87"):
        d1 = "7" + d1[1:]
    if len(d2) == 11 and d2.startswith("87"):
        d2 = "7" + d2[1:]
    return len(d1) >= 10 and len(d2) >= 10 and d1[-10:] == d2[-10:]


def mask_phone(phone: Optional[str]) -> str:
    """Masks a phone number for privacy display (e.g. +7 (701) ***-**-78)."""
    if not phone:
        return "не указан"
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) >= 10:
        return f"+{digits[0]} ({digits[1:4]}) ***-**-{digits[-2:]}"
    return phone[:3] + "***" + phone[-2:] if len(phone) > 5 else "***"


def mask_email(email: Optional[str]) -> str:
    """Masks an email address for privacy display (e.g. a***o@example.com)."""
    if not email or "@" not in email:
        return "не указан"
    parts = str(email).split("@", 1)
    user_part, domain = parts[0], parts[1]
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain}"


def answer_callback_query(callback_query_id: str, text: Optional[str] = None) -> bool:
    """Answers a Telegram inline button callback query."""
    token = get_bot_token()
    if not token or not callback_query_id:
        return False
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        httpx.post(url, json=payload, timeout=5.0)
        return True
    except Exception:
        return False


def should_require_contact_sharing() -> bool:
    """
    Determines whether Telegram contact sharing (request_contact button) is required
    before delivering the 6-digit registration code.
    Enabled whenever ENFORCE_TELEGRAM_CONTACT=1/true or in real non-test bot runs.
    """
    if os.getenv("ENFORCE_TELEGRAM_CONTACT", "").lower() in ("true", "1"):
        return True
    return is_telegram_configured() and os.getenv("TESTING", "").lower() not in ("true", "1")


def send_telegram_message(chat_id: str, text: str, reply_markup: Optional[dict] = None) -> bool:
    """Sends a message to a specific Telegram chat_id, optionally with reply_markup."""

    token = get_bot_token()
    if not token:
        logger.info("Telegram bot token not configured; message not sent")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        response = httpx.post(url, json=payload, timeout=8.0)
        if response.status_code == 200 and response.json().get("ok") is True:
            logger.info(f"✅ Telegram message successfully sent to chat {chat_id}")
            return True
        else:
            logger.error("Telegram API rejected sendMessage (HTTP %s)", response.status_code)
            return False
    except Exception as e:
        logger.error("Telegram sendMessage failed (%s)", type(e).__name__)
        return False


def _deliver_telegram_message(chat_id: str, text: str, reply_markup: Optional[dict] = None) -> bool:
    """
    Calls send_telegram_message with backward compatibility for 2-argument monkeypatched stubs in tests.
    """
    if reply_markup is not None:
        try:
            return send_telegram_message(chat_id, text, reply_markup=reply_markup)
        except TypeError:
            return send_telegram_message(chat_id, text)
    return send_telegram_message(chat_id, text)


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
    return _deliver_telegram_message(chat_id, message)


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
    return _deliver_telegram_message(chat_id, message)


def _handle_unlink_prompt(chat_id: str, db: Session) -> dict:
    from app.models import User
    bound_user = (
        db.query(User)
        .filter(User.telegram_chat_id == chat_id, User.is_verified == True)
        .first()
    )
    if not bound_user:
        _deliver_telegram_message(
            chat_id,
            "ℹ️ Ваш Telegram-аккаунт в данный момент не привязан ни к одной подтвержденной учётной записи.",
            reply_markup={"remove_keyboard": True},
        )
        return {"status": "ok", "action": "already_unbound", "chat_id": chat_id}

    masked_phone = mask_phone(bound_user.phone)
    masked_email = mask_email(bound_user.email)
    reply_text = (
        "⚠️ <b>Подтверждение отвязки Telegram</b>\n\n"
        f"Этот Telegram сейчас привязан к профилю:\n"
        f"• Имя: <b>{bound_user.full_name}</b>\n"
        f"• Номер: <code>{masked_phone}</code>\n"
        f"• Email: <code>{masked_email}</code>\n\n"
        "При отвязке старый аккаунт сохранится, но этот Telegram освободится для регистрации нового аккаунта.\n\n"
        "Для подтверждения нажмите кнопку ниже или отправьте команду:\n"
        "👉 <b>/confirm_unlink</b>"
    )
    inline_keyboard = {
        "inline_keyboard": [
            [{"text": "🔓 Подтвердить отвязку", "callback_data": "confirm_unlink"}],
            [{"text": "❌ Отмена", "callback_data": "cancel_action"}],
        ]
    }
    _deliver_telegram_message(chat_id, reply_text, reply_markup=inline_keyboard)
    return {"status": "ok", "action": "prompt_unlink_confirmation", "chat_id": chat_id}


def _handle_unlink_confirm(chat_id: str, username: Optional[str], db: Session) -> dict:
    from app.models import User, AccountVerificationToken
    bound_user = (
        db.query(User)
        .filter(User.telegram_chat_id == chat_id)
        .first()
    )
    if not bound_user:
        _deliver_telegram_message(
            chat_id,
            "ℹ️ Ваш Telegram-аккаунт уже не привязан ни к одному профилю.",
            reply_markup={"remove_keyboard": True},
        )
        return {"status": "ok", "action": "already_unbound", "chat_id": chat_id}

    old_phone = mask_phone(bound_user.phone)
    bound_user.telegram_chat_id = None
    bound_user.telegram_username = None
    db.commit()

    # Check if there is an active pending registration waiting for this chat_id
    pending_token = (
        db.query(AccountVerificationToken)
        .filter(
            AccountVerificationToken.pending_chat_id == chat_id,
            AccountVerificationToken.is_used == False,
            AccountVerificationToken.telegram_verified == False,
            AccountVerificationToken.expires_at >= datetime.utcnow(),
        )
        .order_by(AccountVerificationToken.created_at.desc(), AccountVerificationToken.id.desc())
        .first()
    )
    if pending_token and pending_token.user:
        pending_user = pending_token.user
        reply_text = (
            f"✅ <b>Telegram успешно отвязан от старого аккаунта ({old_phone})!</b>\n\n"
            f"Теперь ваш Telegram свободен. Продолжаем регистрацию нового аккаунта "
            f"для <b>{pending_user.full_name}</b> (<code>{pending_user.phone}</code>).\n\n"
            "Нажмите кнопку <b>«📱 Подтвердить мой номер телефона»</b> ниже 👇"
        )
        keyboard = {
            "keyboard": [[{"text": "📱 Подтвердить мой номер телефона", "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
        _deliver_telegram_message(chat_id, reply_text, reply_markup=keyboard)
        return {
            "status": "ok",
            "action": "unlinked_and_prompted_contact",
            "chat_id": chat_id,
        }

    reply_text = (
        f"✅ <b>Telegram успешно отвязан от старого аккаунта ({old_phone})!</b>\n\n"
        "Теперь этот Telegram-аккаунт свободен для новой регистрации.\n"
        "Вернитесь на сайт SDU Admissions Assistant и зарегистрируйтесь заново."
    )
    _deliver_telegram_message(chat_id, reply_text, reply_markup={"remove_keyboard": True})
    return {"status": "ok", "action": "unlinked", "chat_id": chat_id}


def _handle_delete_prompt(chat_id: str, db: Session) -> dict:
    from app.models import User
    bound_user = (
        db.query(User)
        .filter(User.telegram_chat_id == chat_id)
        .first()
    )
    if not bound_user:
        _deliver_telegram_message(
            chat_id,
            "ℹ️ Ваш Telegram-аккаунт в данный момент не привязан ни к одному профилю.",
            reply_markup={"remove_keyboard": True},
        )
        return {"status": "ok", "action": "already_unbound", "chat_id": chat_id}

    masked_phone = mask_phone(bound_user.phone)
    masked_email = mask_email(bound_user.email)
    reply_text = (
        "⚠️ <b>Внимание: Удаление старого аккаунта!</b>\n\n"
        f"Вы собираетесь <b>БЕЗВОЗВРАТНО удалить</b> учётную запись:\n"
        f"• Имя: <b>{bound_user.full_name}</b>\n"
        f"• Номер: <code>{masked_phone}</code>\n"
        f"• Email: <code>{masked_email}</code>\n\n"
        "Все данные, профиль абитуриента, сохранённые программы и заявки будут стёрты навсегда.\n\n"
        "Для подтверждения нажмите кнопку ниже или отправьте команду:\n"
        "👉 <b>/confirm_delete</b>"
    )
    inline_keyboard = {
        "inline_keyboard": [
            [{"text": "🗑 Да, навсегда удалить аккаунт", "callback_data": "confirm_delete"}],
            [{"text": "❌ Отмена", "callback_data": "cancel_action"}],
        ]
    }
    _deliver_telegram_message(chat_id, reply_text, reply_markup=inline_keyboard)
    return {"status": "ok", "action": "prompt_delete_confirmation", "chat_id": chat_id}


def _handle_delete_confirm(chat_id: str, username: Optional[str], db: Session) -> dict:
    from app.models import User, AccountVerificationToken, PasswordResetToken
    bound_user = (
        db.query(User)
        .filter(User.telegram_chat_id == chat_id)
        .first()
    )
    if not bound_user:
        _deliver_telegram_message(
            chat_id,
            "ℹ️ Ваш Telegram-аккаунт уже не привязан ни к одному профилю.",
            reply_markup={"remove_keyboard": True},
        )
        return {"status": "ok", "action": "already_unbound", "chat_id": chat_id}

    del_id = bound_user.id
    del_name = bound_user.full_name
    del_phone = mask_phone(bound_user.phone)

    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == del_id).delete(synchronize_session=False)
    db.delete(bound_user)
    db.commit()

    pending_token = (
        db.query(AccountVerificationToken)
        .filter(
            AccountVerificationToken.pending_chat_id == chat_id,
            AccountVerificationToken.is_used == False,
            AccountVerificationToken.telegram_verified == False,
            AccountVerificationToken.expires_at >= datetime.utcnow(),
        )
        .order_by(AccountVerificationToken.created_at.desc(), AccountVerificationToken.id.desc())
        .first()
    )
    if pending_token and pending_token.user:
        pending_user = pending_token.user
        reply_text = (
            f"✅ <b>Старый аккаунт ({del_name}, {del_phone}) успешно удален!</b>\n\n"
            f"Ваш Telegram свободен. Продолжаем регистрацию нового аккаунта "
            f"для <b>{pending_user.full_name}</b> (<code>{pending_user.phone}</code>).\n\n"
            "Нажмите кнопку <b>«📱 Подтвердить мой номер телефона»</b> ниже 👇"
        )
        keyboard = {
            "keyboard": [[{"text": "📱 Подтвердить мой номер телефона", "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
        _deliver_telegram_message(chat_id, reply_text, reply_markup=keyboard)
        return {
            "status": "ok",
            "action": "deleted_and_prompted_contact",
            "chat_id": chat_id,
        }

    reply_text = (
        f"✅ <b>Старый аккаунт ({del_name}, {del_phone}) успешно удален!</b>\n\n"
        "Ваш Telegram-аккаунт полностью свободен. Вы можете начать регистрацию заново на сайте."
    )
    _deliver_telegram_message(chat_id, reply_text, reply_markup={"remove_keyboard": True})
    return {"status": "ok", "action": "account_deleted", "chat_id": chat_id}


def _handle_status(chat_id: str, db: Session) -> dict:
    from app.models import User
    bound_user = (
        db.query(User)
        .filter(User.telegram_chat_id == chat_id, User.is_verified == True)
        .first()
    )
    if bound_user:
        masked_phone = mask_phone(bound_user.phone)
        masked_email = mask_email(bound_user.email)
        reply_text = (
            "🏛️ <b>Информация о привязанном аккаунте SDU:</b>\n\n"
            f"• ФИО: <b>{bound_user.full_name}</b>\n"
            f"• Номер телефона: <code>{masked_phone}</code>\n"
            f"• Email: <code>{masked_email}</code>\n"
            f"• Роль: <code>{bound_user.role}</code>\n"
            f"• Статус: ✅ Подтверждён\n\n"
            "Если вы потеряли доступ к этому номеру или хотите освободить Telegram:\n"
            "👉 /unlink — отвязать Telegram от этого профиля\n"
            "👉 /delete_account — удалить этот профиль навсегда"
        )
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🔓 Отвязать этот Telegram", "callback_data": "confirm_unlink"}],
                [{"text": "🗑 Удалить старый аккаунт", "callback_data": "confirm_delete"}],
            ]
        }
        _deliver_telegram_message(chat_id, reply_text, reply_markup=inline_keyboard)
        return {"status": "ok", "action": "status_displayed", "chat_id": chat_id}

    reply_text = (
        "ℹ️ <b>Ваш Telegram-аккаунт в данный момент не привязан ни к одному профилю.</b>\n\n"
        "Для регистрации перейдите на сайт SDU Admissions Assistant."
    )
    _deliver_telegram_message(chat_id, reply_text, reply_markup={"remove_keyboard": True})
    return {"status": "ok", "action": "status_not_bound", "chat_id": chat_id}


def _handle_help(chat_id: str) -> dict:
    reply_text = (
        "🏛️ <b>SDU Admissions Assistant Bot — Справка</b>\n\n"
        "Доступные команды:\n"
        "• /start — Главное меню бота\n"
        "• /status — Проверить привязанный аккаунт\n"
        "• /unlink — Отвязать Telegram от старого аккаунта\n"
        "• /delete_account — Полностью удалить старый аккаунт\n"
        "• /help — Справка по командам"
    )
    _deliver_telegram_message(chat_id, reply_text)
    return {"status": "ok", "action": "help", "chat_id": chat_id}


def process_telegram_update(update: dict, db: Session) -> dict:
    """
    Processes an incoming Telegram Webhook or Polling update.
    Handles:
      - Callback queries (inline button clicks for unlink, delete account, cancel)
      - Contact sharing (request_contact) for phone ownership verification
      - /start verify_<TOKEN_OR_CODE> and /start reg_<TOKEN_OR_CODE>
      - /start reset_<TOKEN_OR_CODE>
      - /unlink, /delete_account, /status, /help
    """
    from app.models import PasswordResetToken, AccountVerificationToken, User

    msg = update.get("message") or update.get("edited_message")
    callback_query = update.get("callback_query")
    if not msg and not callback_query:
        return {"status": "ignored", "reason": "no message or callback"}

    if callback_query:
        cb_id = str(callback_query.get("id") or "")
        from_user = callback_query.get("from") or {}
        chat = callback_query.get("message", {}).get("chat", {})
        chat_id = str(from_user.get("id") or chat.get("id") or "")
        username = from_user.get("username") or chat.get("username")
        first_name = from_user.get("first_name") or chat.get("first_name", "User")
        text = ""
        contact = None
        data = (callback_query.get("data") or "").strip()
        answer_callback_query(cb_id)
    else:
        chat = msg.get("chat", {})
        from_user = msg.get("from") or {}
        chat_id = str(chat.get("id") or from_user.get("id"))
        username = chat.get("username") or from_user.get("username")
        first_name = from_user.get("first_name") or chat.get("first_name", "User")
        text = (msg.get("text") or "").strip()
        contact = msg.get("contact")
        data = ""

    if text.startswith("/start alerts_"):
        # A forwarded link may be consumed only in a private chat by its owner.
        if chat.get("type") != "private" or str(from_user.get("id")) != chat_id:
            return {"status": "error", "message": "private chat required"}
        from app.services.telegram_binding import consume_link
        linked = consume_link(db, text.removeprefix("/start alerts_").strip(), chat_id)
        send_telegram_message(chat_id, "Telegram linked. Enable deadline alerts in your website profile." if linked
                              else "Link invalid or expired. Request a new link in your website profile.")
        return {"status": "ok" if linked else "error", "action": "alerts_linked" if linked else "invalid_link"}


    # ==========================================
    # COMMANDS & INLINE ACTIONS (UNLINK / DELETE / STATUS)
    # ==========================================
    if data == "cancel_action" or text in ("/cancel", "Отмена"):
        _deliver_telegram_message(chat_id, "❌ Действие отменено.", reply_markup={"remove_keyboard": True})
        return {"status": "ok", "action": "action_cancelled", "chat_id": chat_id}

    if data == "cmd_unlink" or text in ("/unlink", "/reset_telegram", "/reset_binding"):
        return _handle_unlink_prompt(chat_id=chat_id, db=db)

    if data == "confirm_unlink" or text in ("/confirm_unlink", "/confirm_reset_telegram"):
        return _handle_unlink_confirm(chat_id=chat_id, username=username, db=db)

    if data == "cmd_delete_account" or text in ("/delete_account", "/delete_old_account"):
        return _handle_delete_prompt(chat_id=chat_id, db=db)

    if data == "confirm_delete" or text in ("/confirm_delete", "/confirm_delete_account"):
        return _handle_delete_confirm(chat_id=chat_id, username=username, db=db)

    if text in ("/status", "/myaccount", "/profile"):
        return _handle_status(chat_id=chat_id, db=db)

    if text in ("/help", "/info"):
        return _handle_help(chat_id=chat_id)

    # ==========================================
    # CASE A: User shared contact card
    # ==========================================
    if contact:
        contact_user_id = str(contact.get("user_id") or "")
        if contact_user_id != chat_id:
            reply_text = (
                "⛔ <b>Ошибка верификации:</b> Вы отправили чужой контакт. "
                "Пожалуйста, нажмите кнопку <b>«📱 Подтвердить мой номер телефона»</b>, "
                "чтобы поделиться собственным номером Telegram."
            )
            _deliver_telegram_message(chat_id, reply_text)
            return {"status": "error", "reason": "forwarded_contact_rejected"}

        token_entry = (
            db.query(AccountVerificationToken)
            .filter(
                AccountVerificationToken.pending_chat_id == chat_id,
                AccountVerificationToken.is_used == False,
                AccountVerificationToken.expires_at >= datetime.utcnow(),
            )
            .order_by(AccountVerificationToken.created_at.desc(), AccountVerificationToken.id.desc())
            .first()
        )
        if not token_entry:
            reply_text = (
                "❌ <b>Активный запрос на регистрацию не найден или истек.</b> "
                "Пожалуйста, начните регистрацию на сайте SDU Admissions заново."
            )
            _deliver_telegram_message(chat_id, reply_text, reply_markup={"remove_keyboard": True})
            return {"status": "error", "reason": "no_pending_token"}

        # Check 1-to-1 chat_id uniqueness
        existing_bound_user = (
            db.query(User)
            .filter(
                User.telegram_chat_id == chat_id,
                User.is_verified == True,
                User.id != token_entry.user_id,
            )
            .first()
        )
        if existing_bound_user:
            masked_phone = mask_phone(existing_bound_user.phone)
            masked_email = mask_email(existing_bound_user.email)
            reply_text = (
                "⛔ <b>Этот Telegram-аккаунт уже привязан к другому пользователю!</b>\n\n"
                f"👤 <b>Привязанный профиль:</b>\n"
                f"• Имя: <b>{existing_bound_user.full_name}</b>\n"
                f"• Номер: <code>{masked_phone}</code>\n"
                f"• Email: <code>{masked_email}</code>\n\n"
                "Если вы потеряли доступ к старому номеру и хотите зарегистрировать новый аккаунт:\n\n"
                "👉 Нажмите <b>/unlink</b> — отвязать Telegram от старого профиля\n"
                "👉 Нажмите <b>/delete_account</b> — полностью удалить старый аккаунт\n\n"
                "После отвязки вы сможете сразу завершить регистрацию нового аккаунта."
            )
            inline_keyboard = {
                "inline_keyboard": [
                    [{"text": "🔓 Отвязать этот Telegram", "callback_data": "confirm_unlink"}],
                    [{"text": "🗑 Удалить старый аккаунт", "callback_data": "confirm_delete"}],
                ]
            }
            _deliver_telegram_message(chat_id, reply_text, reply_markup=inline_keyboard)
            return {"status": "error", "reason": "telegram_already_bound", "can_unlink": True}

        contact_phone_raw = str(contact.get("phone_number") or "")
        clean_contact_digits = re.sub(r"\D", "", contact_phone_raw)
        user = token_entry.user

        if user and user.phone and not phones_match(contact_phone_raw, user.phone):
            reply_text = (
                f"⛔ <b>Несовпадение номера телефона!</b>\n\n"
                f"На сайте при регистрации был указан номер <code>{user.phone}</code>, "
                f"но ваш Telegram-аккаунт привязан к номеру <code>+{clean_contact_digits}</code>.\n\n"
                f"Пожалуйста, вернитесь на сайт (нажмите <i>«← Back to edit details»</i>), "
                f"укажите свой реальный номер <code>+{clean_contact_digits}</code> и запросите код снова."
            )
            _deliver_telegram_message(chat_id, reply_text)
            return {"status": "error", "reason": "phone_mismatch"}

        # Check that no other verified user already owns this phone
        if clean_contact_digits:
            other_verified_users = (
                db.query(User)
                .filter(
                    User.is_verified == True,
                    User.id != token_entry.user_id,
                    User.phone.isnot(None),
                )
                .all()
            )
            for other_user in other_verified_users:
                if phones_match(other_user.phone, contact_phone_raw):
                    reply_text = (
                        "⛔ <b>Ошибка регистрации!</b>\n\n"
                        "Этот номер телефона уже привязан к другому подтвержденному аккаунту."
                    )
                    _deliver_telegram_message(chat_id, reply_text, reply_markup={"remove_keyboard": True})
                    return {"status": "error", "reason": "phone_already_registered"}

        # Phone matches! Mark token verified and bind Telegram account
        token_entry.telegram_verified = True
        if user:
            user.telegram_chat_id = chat_id
            if username:
                user.telegram_username = username
        db.commit()

        reply_text = (
            f"✅ <b>Номер телефона и Telegram-аккаунт успешно подтверждены!</b>\n\n"
            f"Здравствуйте, <b>{user.full_name if user else first_name}</b>!\n"
            f"Ваш 6-значный код активации аккаунта:\n\n"
            f"👉 <code>{token_entry.code}</code>\n\n"
            f"⏱ <i>Код действителен в течение 15 минут. Введите его в окне подтверждения на сайте.</i>"
        )
        _deliver_telegram_message(chat_id, reply_text, reply_markup={"remove_keyboard": True})
        return {
            "status": "ok",
            "action": "registration_code_delivered",
            "chat_id": chat_id,
            "code": token_entry.code,
        }

    # ==========================================
    # CASE B: /start verify_<ARG> or /start reg_<ARG>
    # ==========================================
    if text.startswith("/start verify_") or text.startswith("/start reg_"):
        arg = text.replace("/start verify_", "").replace("/start reg_", "").strip()
        token_entry = (
            db.query(AccountVerificationToken)
            .filter(
                AccountVerificationToken.is_used == False,
                or_(
                    AccountVerificationToken.session_token == arg,
                    AccountVerificationToken.code == arg,
                ),
            )
            .order_by(AccountVerificationToken.created_at.desc(), AccountVerificationToken.id.desc())
            .first()
        )

        if not token_entry or token_entry.expires_at < datetime.utcnow():
            reply_text = (
                "❌ <b>Код подтверждения недействителен или истек.</b>\n\n"
                "Пожалуйста, запросите новый код подтверждения на сайте SDU Admissions."
            )
            _deliver_telegram_message(chat_id, reply_text)
            return {"status": "error", "message": "code invalid or expired"}

        token_entry.pending_chat_id = chat_id
        db.commit()

        # Check 1-to-1 Telegram Account Uniqueness
        existing_bound_user = (
            db.query(User)
            .filter(
                User.telegram_chat_id == chat_id,
                User.is_verified == True,
                User.id != token_entry.user_id,
            )
            .first()
        )
        if existing_bound_user:
            masked_phone = mask_phone(existing_bound_user.phone)
            masked_email = mask_email(existing_bound_user.email)
            reply_text = (
                "⛔ <b>Этот Telegram-аккаунт уже привязан к другому профилю!</b>\n\n"
                f"👤 <b>Привязанный профиль:</b>\n"
                f"• Имя: <b>{existing_bound_user.full_name}</b>\n"
                f"• Номер: <code>{masked_phone}</code>\n"
                f"• Email: <code>{masked_email}</code>\n\n"
                "Если вы потеряли доступ к старому номеру и хотите зарегистрировать новый аккаунт:\n\n"
                "👉 Нажмите <b>/unlink</b> — чтобы отвязать Telegram от старого профиля\n"
                "👉 Нажмите <b>/delete_account</b> — чтобы полностью удалить старый аккаунт\n\n"
                "После отвязки вы сможете сразу завершить регистрацию нового аккаунта."
            )
            inline_keyboard = {
                "inline_keyboard": [
                    [{"text": "🔓 Отвязать этот Telegram", "callback_data": "confirm_unlink"}],
                    [{"text": "🗑 Удалить старый аккаунт", "callback_data": "confirm_delete"}],
                ]
            }
            _deliver_telegram_message(chat_id, reply_text, reply_markup=inline_keyboard)
            return {"status": "error", "reason": "telegram_already_bound", "can_unlink": True}

        user = token_entry.user

        if should_require_contact_sharing():
            db.commit()
            reply_text = (
                f"🏛️ <b>SDU Admissions Assistant — Проверка номера</b>\n\n"
                f"Здравствуйте, <b>{user.full_name if user else first_name}</b>!\n"
                f"Вы регистрируете аккаунт на номер: <code>{user.phone if user else ''}</code>.\n\n"
                f"Для защиты от фейковых регистраций подтвердите, что этот номер принадлежит вашему Telegram-аккаунту — "
                f"нажмите кнопку <b>«📱 Подтвердить мой номер телефона»</b> внизу экрана 👇"
            )
            keyboard = {
                "keyboard": [[{"text": "📱 Подтвердить мой номер телефона", "request_contact": True}]],
                "resize_keyboard": True,
                "one_time_keyboard": True,
            }
            _deliver_telegram_message(chat_id, reply_text, reply_markup=keyboard)
            return {"status": "ok", "action": "awaiting_contact_verification", "chat_id": chat_id}

        # Legacy unit test mode where contact sharing is not enforced
        token_entry.telegram_verified = True
        if user:
            user.telegram_chat_id = chat_id
            if username:
                user.telegram_username = username
        db.commit()

        reply_text = (
            f"🏛️ <b>SDU Admissions Assistant</b>\n\n"
            f"Здравствуйте, <b>{user.full_name if user else first_name}</b>!\n"
            f"Ваш 6-значный проверочный код подтверждения регистрации:\n\n"
            f"👉 <code>{token_entry.code}</code>\n\n"
            f"⏱ <i>Код действителен в течение 15 минут.</i>\n"
            f"Введите этот код в окне подтверждения на сайте для активации аккаунта."
        )
        _deliver_telegram_message(chat_id, reply_text)
        return {
            "status": "ok",
            "action": "registration_code_delivered",
            "chat_id": chat_id,
            "code": token_entry.code,
        }

    # ==========================================
    # CASE C: /start reset_<ARG>
    # ==========================================
    elif text.startswith("/start reset_"):
        arg = text.replace("/start reset_", "").strip()

        token_entry = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.is_used == False,
                or_(
                    PasswordResetToken.session_token == arg,
                    PasswordResetToken.code == arg,
                ),
            )
            .order_by(PasswordResetToken.id.desc())
            .first()
        )

        if not token_entry or token_entry.expires_at < datetime.utcnow():
            reply_text = (
                "❌ <b>Код недействителен или истек.</b>\n\n"
                "Пожалуйста, запросите новый код сброса пароля на сайте SDU Admissions."
            )
            _deliver_telegram_message(chat_id, reply_text)
            return {"status": "error", "message": "code invalid or expired"}

        user = token_entry.user
        if user:
            if user.telegram_chat_id and str(user.telegram_chat_id) != chat_id:
                reply_text = (
                    "⛔ <b>Отказано в доступе!</b>\n\n"
                    "Этот запрос на сброс пароля инициирован для аккаунта, который привязан к другому Telegram-профилю.\n"
                    "Откройте ссылку с того Telegram-аккаунта, который вы привязывали при регистрации."
                )
                _deliver_telegram_message(chat_id, reply_text)
                return {"status": "error", "reason": "telegram_mismatch"}

            if not user.telegram_chat_id:
                existing_bound_user = (
                    db.query(User)
                    .filter(
                        User.telegram_chat_id == chat_id,
                        User.is_verified == True,
                        User.id != user.id,
                    )
                    .first()
                )
                if existing_bound_user:
                    masked_phone = mask_phone(existing_bound_user.phone)
                    reply_text = (
                        "⛔ <b>Ошибка привязки Telegram!</b>\n\n"
                        f"Этот Telegram-аккаунт уже привязан к другому профилю ({masked_phone}).\n"
                        "Отправьте команду /unlink или /delete_account, чтобы освободить Telegram."
                    )
                    inline_keyboard = {
                        "inline_keyboard": [
                            [{"text": "🔓 Отвязать этот Telegram", "callback_data": "confirm_unlink"}],
                            [{"text": "🗑 Удалить старый аккаунт", "callback_data": "confirm_delete"}],
                        ]
                    }
                    _deliver_telegram_message(chat_id, reply_text, reply_markup=inline_keyboard)
                    return {"status": "error", "reason": "telegram_already_bound", "can_unlink": True}

                user.telegram_chat_id = chat_id
                if username:
                    user.telegram_username = username
                db.commit()
            elif username and user.telegram_username != username:
                user.telegram_username = username
                db.commit()

        reply_text = (
            f"🏛️ <b>SDU Admissions Assistant</b>\n\n"
            f"Здравствуйте, <b>{user.full_name if user else first_name}</b>!\n"
            f"Ваш 6-значный проверочный код подтвержден:\n\n"
            f"👉 <code>{token_entry.code}</code>\n\n"
            f"Введите этот код в окне сброса пароля на сайте для установки нового пароля."
        )
        _deliver_telegram_message(chat_id, reply_text)
        return {
            "status": "ok",
            "action": "reset_code_delivered",
            "chat_id": chat_id,
            "code": token_entry.code,
        }

    elif text.startswith("/start"):
        bound_user = (
            db.query(User)
            .filter(User.telegram_chat_id == chat_id, User.is_verified == True)
            .first()
        )
        if bound_user:
            masked_phone = mask_phone(bound_user.phone)
            reply_text = (
                f"🏛️ <b>SDU Admissions Assistant Bot</b>\n\n"
                f"Привет, <b>{first_name}</b>!\n"
                f"Ваш Telegram привязан к аккаунту: <b>{bound_user.full_name}</b> (<code>{masked_phone}</code>).\n\n"
                f"Доступные действия:\n"
                f"• /status — Информация о привязанном профиле\n"
                f"• /unlink — Отвязать Telegram от старого номера\n"
                f"• /delete_account — Удалить старый аккаунт\n"
                f"• /help — Справка по командам"
            )
        else:
            reply_text = (
                f"🏛️ <b>SDU Admissions Assistant Bot</b>\n\n"
                f"Привет, <b>{first_name}</b>!\n"
                f"Я официальный бот приемной комиссии SDU University.\n\n"
                f"Здесь вы можете:\n"
                f"• Подтвердить свой номер телефона при регистрации\n"
                f"• Получать коды восстановления пароля\n"
                f"• Получать уведомления о дедлайнах поступления\n\n"
                f"Для регистрации или сброса пароля перейдите на сайт SDU Admissions Assistant."
            )
        _deliver_telegram_message(chat_id, reply_text)
        return {"status": "ok", "action": "welcome"}

    return {"status": "ok", "action": "unhandled_command"}


async def register_telegram_webhook(webhook_url: str) -> dict:
    """Register an HTTPS webhook URL with Telegram Bot API for multi-worker production."""
    token = get_bot_token()
    if not token:
        return {"ok": False, "error": "Telegram bot token not configured"}
    base_url = f"https://api.telegram.org/bot{token}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{base_url}/setWebhook", json={"url": webhook_url, "secret_token": os.environ["TELEGRAM_WEBHOOK_SECRET"]})
        return resp.json()


def _try_acquire_poller_lock():
    """
    Acquire an OS-level non-blocking file lock so that under multi-worker Uvicorn (--workers N),
    only a single worker process runs Telegram long-polling.
    Returns the open file handle if acquired, or None if another worker holds the lock.
    """
    from pathlib import Path
    lock_dir = Path(__file__).resolve().parent.parent / "data"
    lock_dir.mkdir(exist_ok=True)
    lock_path = lock_dir / "telegram_poller.lock"
    fh = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except (OSError, IOError):
        fh.close()
        return None


async def start_telegram_polling():
    """
    Background asynchronous polling worker for Telegram Bot updates.
    Protected by an OS-level lock so multi-worker deployments never collide on getUpdates.
    """
    import asyncio

    mode = os.getenv("TELEGRAM_MODE", "polling").strip().lower()
    if mode in ("webhook", "worker_disabled", "disabled", "off"):
        logger.info(f"ℹ️ Telegram polling skipped in web process (TELEGRAM_MODE={mode}).")
        return

    token = get_bot_token()
    if not token:
        logger.info("ℹ️ Telegram bot token not configured. Background polling will not start.")
        return

    lock_handle = _try_acquire_poller_lock()
    if lock_handle is None:
        logger.info("ℹ️ Telegram poller lock held by primary worker; skipping duplicate poller in this worker.")
        return

    logger.info(f"🚀 Telegram Bot Poller starting for @{get_bot_username()} (PID {os.getpid()})...")
    offset = 0
    base_url = f"https://api.telegram.org/bot{token}"

    try:
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
    finally:
        try:
            lock_handle.close()
        except Exception:
            pass
