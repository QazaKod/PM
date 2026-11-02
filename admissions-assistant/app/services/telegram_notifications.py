"""US20: Telegram Push Alerts Service for Admissions Deadlines.

Dispatches automated reminders to verified applicants prior to critical
admissions milestones, respecting Almaty quiet hours (22:00 – 08:00).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import User, TelegramBinding, DeadlineDelivery
from sqlalchemy.exc import IntegrityError
from html import escape
from hashlib import sha256
from urllib.parse import urlparse
import os
import asyncio
from app.services.deadlines import get_upcoming_deadlines_for_alert
from app import telegram_service

logger = logging.getLogger("admissions_api")

try:
    from zoneinfo import ZoneInfo
    ALMATY_TZ = ZoneInfo("Asia/Almaty")
    datetime.now(ALMATY_TZ)
except Exception:
    ALMATY_TZ = timezone(timedelta(hours=5))


def checklist_url() -> str:
    base = os.getenv("PUBLIC_APP_URL", "").rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("PUBLIC_APP_URL must be an HTTPS application URL")
    return base + "/#guide"


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Dispatch with a one-click checklist button."""
    keyboard = {"inline_keyboard": [[{"text": "Открыть чеклист поступления", "url": checklist_url()}]]}
    return telegram_service.send_telegram_message(chat_id, text, reply_markup=keyboard)


def get_almaty_now() -> datetime:
    """Returns current datetime in Asia/Almaty timezone."""
    return datetime.now(ALMATY_TZ)


def is_almaty_quiet_hours(dt: Optional[datetime] = None) -> bool:
    """Checks whether the given time falls within quiet hours (22:00 - 08:00 Almaty time)."""
    current_dt = dt or get_almaty_now()
    if current_dt.tzinfo is not None:
        current_dt = current_dt.astimezone(ALMATY_TZ)
    hour = current_dt.hour
    return hour >= 22 or hour < 8


def format_deadline_alert_html(user_name: str, deadline: Dict, days_ahead: int) -> str:
    """Formats a localized HTML alert message for Telegram push notification."""
    user_name = escape(user_name)
    deadline = {key: escape(str(value), quote=True) if value is not None else "" for key, value in deadline.items()}
    action = urlparse(deadline["action_url"])
    if action.scheme != "https" or not action.hostname:
        raise ValueError("Deadline action URL must use HTTPS")
    alert_type = deadline.get("alert_type", "closing")
    if alert_type == "opening":
        timing_line = f"⏳ <b>До открытия этапа осталось:</b> {days_ahead} дн. (старт {deadline['date_start']})"
    else:
        timing_line = f"⏳ <b>До окончания дедлайна осталось:</b> {days_ahead} дн. (до {deadline['date_end']})"

    lines = [
        "🏛️ <b>SDU Admissions: Напоминание о дедлайне</b>\n",
        f"Здравствуйте, <b>{user_name}</b>!",
        "Напоминаем о ключевом сроке приемной кампании SDU:\n",
        f"📌 <b>{deadline['title']}</b>",
        f"🗓 <b>Период:</b> {deadline['date_start']} — {deadline['date_end']}",
        timing_line,
        f"\nℹ️ {deadline['description']}",
    ]

    if deadline.get("passed_advice") and deadline.get("status") == "passed":
        lines.append(f"\n💡 <i>Совет: {deadline['passed_advice']}</i>")

    lines.append(f"\n🔗 <a href=\"{deadline['action_url']}\">Официальный портал SDU</a>")
    return "\n".join(lines)


def send_deadline_alerts(
    db: Session,
    target_days_ahead: int = 3,
    force_send: bool = False,
    reference_date: Optional[datetime] = None,
) -> Dict:
    """Dispatches Telegram notifications for upcoming deadlines occurring in target_days_ahead days."""
    if not telegram_service.is_telegram_configured():
        return {"dispatched": 0, "skipped": 0, "deadlines_checked": 0, "reason": "Telegram not configured"}
    try:
        checklist_url()
    except ValueError:
        return {"dispatched": 0, "skipped": 0, "deadlines_checked": 0, "reason": "Configure HTTPS PUBLIC_APP_URL"}
    ref_dt = reference_date or get_almaty_now()
    if isinstance(ref_dt, datetime) and ref_dt.tzinfo is not None:
        ref_dt = ref_dt.astimezone(ALMATY_TZ)
    ref_date = ref_dt.date() if isinstance(ref_dt, datetime) else ref_dt

    deadlines = get_upcoming_deadlines_for_alert(days_ahead=target_days_ahead, reference_date=ref_date)
    deadlines_checked = len(deadlines)

    if deadlines_checked == 0:
        logger.info(f"ℹ️ No admissions deadlines occurring in {target_days_ahead} days.")
        return {
            "dispatched": 0,
            "skipped": 0,
            "deadlines_checked": 0,
            "message": f"No deadlines occurring exactly in {target_days_ahead} days.",
        }

    # Quiet hours check: Almaty 22:00 to 08:00
    if not force_send and is_almaty_quiet_hours(ref_dt if isinstance(ref_dt, datetime) else None):
        logger.info("🌙 Almaty quiet hours active (22:00 - 08:00). Deadline alerts suppressed.")
        return {
            "dispatched": 0,
            "skipped": 0,
            "deadlines_checked": deadlines_checked,
            "reason": "Quiet hours (22:00-08:00 Almaty time). Alerts suppressed. Pass force_send=True to override.",
        }

    # Find verified users with active telegram notifications
    users = db.query(User).join(TelegramBinding, TelegramBinding.user_id == User.id).filter(
        User.role == "applicant",
        TelegramBinding.verified_at.isnot(None),
        TelegramBinding.chat_id == User.telegram_chat_id,
        User.is_active == True,
        User.is_verified == True,
        User.telegram_chat_id.isnot(None),
        User.telegram_chat_id != "",
        User.telegram_notifications_enabled == True,
    ).all()

    dispatched = 0
    skipped = 0

    for user in users:
        user_name = user.full_name or "Абитуриент"
        for dl in deadlines:
            msg_html = format_deadline_alert_html(user_name, dl, target_days_ahead)
            event_date = dl["date_start"] if dl.get("alert_type") == "opening" else dl["date_end"]
            key = sha256(f"{user.telegram_chat_id}|{dl['id']}|{event_date}|{dl.get('alert_type', 'closing')}|{target_days_ahead}".encode()).hexdigest()
            delivery = DeadlineDelivery(key=key, chat_id=user.telegram_chat_id,
                                        deadline_id=dl["id"], event_date=event_date,
                                        days_ahead=target_days_ahead, state="claimed")
            try:
                db.add(delivery)
                db.commit()  # Unique claim shared by manual and automatic runs.
            except IntegrityError:
                db.rollback()
                skipped += 1
                continue
            try:
                sent = send_telegram_message(user.telegram_chat_id, msg_html)
            except Exception:
                # Telegram may have accepted a request even when the client
                # timed out. Never blindly resend an uncertain delivery.
                logger.exception("Deadline delivery failed; inspect ledger key %s", key)
                sent = False
            delivery.state = "sent" if sent else "uncertain"
            db.commit()
            if sent:
                dispatched += 1
            else:
                skipped += 1

    logger.info(
        f"📢 Dispatched deadline alerts summary: dispatched={dispatched}, "
        f"skipped={skipped}, deadlines_checked={deadlines_checked}, users_notified={len(users)}"
    )

    return {
        "dispatched": dispatched,
        "skipped": skipped,
        "deadlines_checked": deadlines_checked,
        "users_count": len(users),
    }


def run_reminder_cycle(reference_date=None):
    """One safe cycle for cron or the worker; no network when unconfigured."""
    if not telegram_service.is_telegram_configured() or not os.getenv("PUBLIC_APP_URL"):
        return {"disabled": "Configure TELEGRAM_BOT_TOKEN and PUBLIC_APP_URL"}
    from app.db_session import SessionLocal
    with SessionLocal() as db:
        return {str(days): send_deadline_alerts(db, days, reference_date=reference_date) for days in (3, 1)}


async def start_deadline_reminders():
    """Minute polling permits same-day catch-up after quiet hours or restart.

    Dates in the existing calendar have no cutoff time: reminders mean calendar
    days, not an invented exact 72-hour cutoff. Persistent claims deduplicate.
    """
    while True:
        try:
            await asyncio.to_thread(run_reminder_cycle)
        except Exception:
            logger.exception("Deadline reminder cycle failed")
        await asyncio.sleep(60)
