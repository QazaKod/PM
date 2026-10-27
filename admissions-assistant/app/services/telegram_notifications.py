"""US20: Telegram Push Alerts Service for Admissions Deadlines.

Dispatches automated reminders to verified applicants prior to critical
admissions milestones, respecting Almaty quiet hours (22:00 – 08:00).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import User
from app.services.deadlines import get_upcoming_deadlines_for_alert
from app import telegram_service

logger = logging.getLogger("admissions_api")

try:
    from zoneinfo import ZoneInfo
    ALMATY_TZ = ZoneInfo("Asia/Almaty")
    datetime.now(ALMATY_TZ)
except Exception:
    ALMATY_TZ = timezone(timedelta(hours=5))


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Dispatches message via telegram_service with mockability."""
    return telegram_service.send_telegram_message(chat_id, text)


def get_almaty_now() -> datetime:
    """Returns current datetime in Asia/Almaty timezone."""
    return datetime.now(ALMATY_TZ)


def is_almaty_quiet_hours(dt: Optional[datetime] = None) -> bool:
    """Checks whether the given time falls within quiet hours (22:00 - 08:00 Almaty time)."""
    current_dt = dt or get_almaty_now()
    hour = current_dt.hour
    return hour >= 22 or hour < 8


def format_deadline_alert_html(user_name: str, deadline: Dict, days_ahead: int) -> str:
    """Formats a localized HTML alert message for Telegram push notification."""
    alert_type = deadline.get("alert_type", "closing")
    if alert_type == "opening":
        timing_line = f"⏳ <b>До открытия этапа осталось:</b> {days_ahead} дн. (старт {deadline['date_start']})"
    else:
        timing_line = f"⏳ <b>До окончания дедлайна осталось:</b> {days_ahead} дн. (до {deadline['date_end']})"

    lines = [
        "🏛️ <b>SDU Admissions: Напоминание о дедлайне</b>\n",
        f"Здравствуйте, <b>{user_name}</b>!",
        "Напоминаем о ключевом сроке приемной кампании SDU 2026-2027:\n",
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
    ref_dt = reference_date or get_almaty_now()
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
    users = db.query(User).filter(
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
            sent = send_telegram_message(user.telegram_chat_id, msg_html)
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
