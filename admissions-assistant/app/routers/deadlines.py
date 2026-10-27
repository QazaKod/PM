"""US8 & US20: Deadlines & Academic Calendar Router (/deadlines).

Endpoints:
  - GET /deadlines: List official admissions campaign milestones with filtering and localization
  - GET /deadlines/calendar: Monthly calendar grid with color-coded daily events
  - POST /deadlines/trigger-alerts: Trigger Telegram deadline reminders (staff/admin only)
  - PATCH /deadlines/preferences: Toggle user deadline notification preferences
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import User
from app.schemas import (
    DeadlinesListResponse,
    CalendarResponse,
    NotificationPreferenceRequest,
    NotificationPreferenceResponse,
)
from app.security import get_current_user, require_role
from app.services import deadlines as deadline_service
from app.services import telegram_notifications

logger = logging.getLogger("admissions_api")

router = APIRouter(prefix="/deadlines", tags=["Deadlines & Calendar"])


@router.get("", response_model=DeadlinesListResponse)
def get_deadlines_list(
    category: Optional[str] = Query(None, description="Filter by category ('grant', 'unt', 'contract', 'dormitory', 'olympiad', 'exam')"),
    degree_level: Optional[str] = Query(None, description="Filter by degree level ('all', 'undergraduate', 'graduate')"),
    lang: str = Query("ru", description="Response language ('ru', 'kk', 'en')"),
):
    """Retrieve official SDU admissions deadlines with dynamic statuses and days remaining."""
    items = deadline_service.get_all_deadlines(
        category=category,
        degree_level=degree_level,
        lang=lang,
    )
    return {
        "total": len(items),
        "reference_date": str(deadline_service.local_today()),
        "deadlines": items,
    }


@router.get("/calendar", response_model=CalendarResponse)
def get_deadlines_calendar(
    year: int = Query(2026, description="Intake academic year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Specific month (1-12)"),
    lang: str = Query("ru", description="Response language ('ru', 'kk', 'en')"),
):
    """Retrieve calendar grid representation grouped by month with daily color-coded deadline events."""
    return deadline_service.get_calendar_events(
        year=year,
        month=month,
        lang=lang,
    )


@router.post("/trigger-alerts")
def trigger_deadline_alerts(
    days_ahead: int = Query(3, ge=1, le=60, description="Target days ahead for deadline reminder"),
    force_send: bool = Query(False, description="Override quiet hours (22:00-08:00 Almaty time)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Dispatch Telegram push alerts for deadlines occurring in days_ahead days (staff only)."""
    result = telegram_notifications.send_deadline_alerts(
        db=db,
        target_days_ahead=days_ahead,
        force_send=force_send,
    )
    return result


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    payload: NotificationPreferenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle current user's Telegram deadline notification preferences."""
    current_user.telegram_notifications_enabled = payload.telegram_notifications_enabled
    db.commit()
    db.refresh(current_user)

    state_str = "включены" if current_user.telegram_notifications_enabled else "отключены"
    return {
        "status": "success",
        "telegram_notifications_enabled": current_user.telegram_notifications_enabled,
        "telegram_chat_id": current_user.telegram_chat_id,
        "message": f"Уведомления о дедлайнах успешно {state_str}.",
    }
