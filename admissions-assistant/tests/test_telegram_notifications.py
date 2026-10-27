"""US20: Telegram Push Alerts Service Test Suite."""

import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.db_session import SessionLocal
from app.models import User
from app.security import hash_password, create_access_token
from app.services.telegram_notifications import (
    ALMATY_TZ,
    is_almaty_quiet_hours,
    format_deadline_alert_html,
    send_deadline_alerts,
)
from app.services import telegram_notifications


client = TestClient(app)


def _create_test_user(
    role: str = "applicant",
    is_verified: bool = True,
    chat_id: str = "12345678",
    notif_enabled: bool = True,
) -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"tg_{uuid.uuid4().hex[:8]}@sdu.edu.kz",
            hashed_password=hash_password("Secret123!"),
            full_name="Telegram Applicant",
            role=role,
            is_active=True,
            is_verified=is_verified,
            telegram_chat_id=chat_id,
            telegram_notifications_enabled=notif_enabled,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token({"sub": str(user.id)})
        return user, token
    finally:
        db.close()


def test_user_telegram_notifications_enabled_default():
    """Verify newly registered user has telegram_notifications_enabled = True by default."""
    user, _ = _create_test_user()
    assert user.telegram_notifications_enabled is True


def test_notification_preference_toggle_endpoints():
    """Verify applicant can toggle telegram notification preference via API."""
    user, token = _create_test_user()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Disable notifications via /auth/notifications/preferences
    res_off = client.patch(
        "/auth/notifications/preferences",
        json={"telegram_notifications_enabled": False},
        headers=headers,
    )
    assert res_off.status_code == 200
    assert res_off.json()["telegram_notifications_enabled"] is False

    # Verify persisted in database
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user.id).first()
        assert db_user.telegram_notifications_enabled is False
    finally:
        db.close()

    # 2. Re-enable via /deadlines/preferences
    res_on = client.patch(
        "/deadlines/preferences",
        json={"telegram_notifications_enabled": True},
        headers=headers,
    )
    assert res_on.status_code == 200
    assert res_on.json()["telegram_notifications_enabled"] is True


def test_almaty_quiet_hours_detection():
    """Verify Almaty quiet hours suppression between 22:00 and 08:00."""
    # 23:30 -> quiet hours
    late_night = datetime(2026, 7, 10, 23, 30, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(late_night) is True

    # 04:00 -> quiet hours
    early_morning = datetime(2026, 7, 10, 4, 0, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(early_morning) is True

    # 14:00 -> daytime active hours
    daytime = datetime(2026, 7, 10, 14, 0, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(daytime) is False


def test_send_deadline_alerts_dispatch(monkeypatch):
    """Verify deadline alerts dispatch to eligible users and skip disabled ones."""
    sent_messages = []

    def mock_send_telegram(chat_id, text):
        sent_messages.append((chat_id, text))
        return True

    monkeypatch.setattr(telegram_notifications, "send_telegram_message", mock_send_telegram)

    # Create two users: one enabled, one disabled
    user_enabled, _ = _create_test_user(chat_id="chat_active_99", notif_enabled=True)
    user_disabled, _ = _create_test_user(chat_id="chat_muted_88", notif_enabled=False)

    db = SessionLocal()
    try:
        # Reference date 2026-07-10: State grant competition starts in 3 days (2026-07-13)
        ref_dt = datetime(2026, 7, 10, 12, 0, tzinfo=ALMATY_TZ)

        summary = send_deadline_alerts(
            db=db,
            target_days_ahead=3,
            force_send=True,
            reference_date=ref_dt,
        )

        assert summary["deadlines_checked"] >= 1
        assert summary["dispatched"] >= 1
        # Enabled user received message, disabled user did not
        chat_ids_received = [c for c, _ in sent_messages]
        assert "chat_active_99" in chat_ids_received
        assert "chat_muted_88" not in chat_ids_received
    finally:
        db.close()


def test_quiet_hours_suppression_and_force_override(monkeypatch):
    """Verify alerts are suppressed during quiet hours unless force_send is set."""
    sent_messages = []
    monkeypatch.setattr(telegram_notifications, "send_telegram_message", lambda c, t: sent_messages.append((c, t)) or True)

    _create_test_user(chat_id="chat_night_77", notif_enabled=True)

    db = SessionLocal()
    try:
        # 23:00 Almaty time -> quiet hours
        night_dt = datetime(2026, 7, 10, 23, 0, tzinfo=ALMATY_TZ)

        # 1. Without force_send -> suppressed
        summary_quiet = send_deadline_alerts(
            db=db,
            target_days_ahead=3,
            force_send=False,
            reference_date=night_dt,
        )
        assert summary_quiet["dispatched"] == 0
        assert "Quiet hours" in summary_quiet.get("reason", "")

        # 2. With force_send -> sent
        summary_forced = send_deadline_alerts(
            db=db,
            target_days_ahead=3,
            force_send=True,
            reference_date=night_dt,
        )
        assert summary_forced["dispatched"] >= 1
    finally:
        db.close()


def test_trigger_alerts_api_security(monkeypatch):
    """Verify /deadlines/trigger-alerts is restricted to staff."""
    monkeypatch.setattr(telegram_notifications, "send_telegram_message", lambda c, t: True)

    # Unauthenticated -> 401
    res_unauth = client.post("/deadlines/trigger-alerts?days_ahead=3")
    assert res_unauth.status_code == 401

    # Applicant -> 403
    _, applicant_token = _create_test_user(role="applicant")
    res_applicant = client.post(
        "/deadlines/trigger-alerts?days_ahead=3",
        headers={"Authorization": f"Bearer {applicant_token}"},
    )
    assert res_applicant.status_code == 403

    # Admin -> 200
    _, admin_token = _create_test_user(role="admin")
    res_admin = client.post(
        "/deadlines/trigger-alerts?days_ahead=3&force_send=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    assert "deadlines_checked" in res_admin.json()


def test_us20_scenario1_impending_deadline_alert_1day_and_3days(monkeypatch):
    """US20 Scenario 1: Scheduled deadline alert for verified Telegram user when a deadline is impending (3 days / 72h and 1 day / 24h)."""
    sent_messages = []
    monkeypatch.setattr(telegram_notifications, "send_telegram_message", lambda chat_id, text: sent_messages.append((chat_id, text)) or True)

    user, _ = _create_test_user(chat_id="chat_impending_123", notif_enabled=True)

    db = SessionLocal()
    try:
        # Case A: 1 day / 24h away (State grant competition ends 2026-07-20 -> reference is 2026-07-19)
        ref_1day = datetime(2026, 7, 19, 11, 0, tzinfo=ALMATY_TZ)
        summary_1day = send_deadline_alerts(
            db=db,
            target_days_ahead=1,
            force_send=True,
            reference_date=ref_1day,
        )
        assert summary_1day["deadlines_checked"] >= 1
        assert summary_1day["dispatched"] >= 1

        # Check message content for 1-day alert
        msg_1day = [text for cid, text in sent_messages if cid == "chat_impending_123"][-1]
        assert "SDU Admissions" in msg_1day
        assert "1 дн." in msg_1day
        assert "Конкурс государственных образовательных грантов" in msg_1day
        assert "https://egov.kz" in msg_1day or "http" in msg_1day

        # Case B: 3 days / 72h away (State grant competition ends 2026-07-20 -> reference is 2026-07-17)
        ref_3days = datetime(2026, 7, 17, 11, 0, tzinfo=ALMATY_TZ)
        summary_3days = send_deadline_alerts(
            db=db,
            target_days_ahead=3,
            force_send=True,
            reference_date=ref_3days,
        )
        assert summary_3days["deadlines_checked"] >= 1
        assert summary_3days["dispatched"] >= 1

        # Check message content for 3-days alert
        msg_3days = [text for cid, text in sent_messages if cid == "chat_impending_123"][-1]
        assert "SDU Admissions" in msg_3days
        assert "3 дн." in msg_3days
        assert "Конкурс государственных образовательных грантов" in msg_3days
    finally:
        db.close()


def test_us20_scenario2_muted_applicant_skipped_and_unverified_skipped(monkeypatch):
    """US20 Scenario 2: Applicant who opted out or is unverified/lacks chat_id is strictly skipped."""
    sent_cids = []
    monkeypatch.setattr(telegram_notifications, "send_telegram_message", lambda chat_id, text: sent_cids.append(chat_id) or True)

    # 1. Verified + Enabled
    _create_test_user(chat_id="chat_ok", notif_enabled=True, is_verified=True)
    # 2. Verified + Disabled (opted out)
    _create_test_user(chat_id="chat_optout", notif_enabled=False, is_verified=True)
    # 3. Unverified + Enabled
    _create_test_user(chat_id="chat_unverified", notif_enabled=True, is_verified=False)
    # 4. Verified + Enabled but empty chat_id
    _create_test_user(chat_id="", notif_enabled=True, is_verified=True)

    db = SessionLocal()
    try:
        ref_dt = datetime(2026, 7, 17, 12, 0, tzinfo=ALMATY_TZ)
        summary = send_deadline_alerts(
            db=db,
            target_days_ahead=3,
            force_send=True,
            reference_date=ref_dt,
        )
        assert summary["dispatched"] >= 1
        assert "chat_ok" in sent_cids
        assert "chat_optout" not in sent_cids
        assert "chat_unverified" not in sent_cids
        assert "" not in sent_cids
    finally:
        db.close()

