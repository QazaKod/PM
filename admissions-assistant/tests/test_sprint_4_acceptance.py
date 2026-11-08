"""
Sprint 4 Comprehensive Acceptance & End-to-End Test Suite:
- US8: Deadlines & Calendar (Edge cases, invalid queries, calendar boundaries, Kazakh language NLP)
- US13: Manage FAQ Database (Search, filters, validation, hot-reload, RBAC deletion)
- US20: Telegram Push Alerts (Template formatting, boundary quiet hours, multi-user batching, force override)
"""
import uuid
from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_session import SessionLocal
from app.models import User, FAQ
from app.security import hash_password, create_access_token
from app import chatbot
from app.services.deadlines import (
    get_all_deadlines,
    get_calendar_events,
    get_upcoming_deadlines_for_alert,
)
from app.services.telegram_notifications import (
    ALMATY_TZ,
    is_almaty_quiet_hours,
    format_deadline_alert_html,
    send_deadline_alerts,
)

client = TestClient(app)


def _create_user(role: str = "applicant", chat_id: str = None, enabled: bool = True) -> tuple[User, str]:
    db = SessionLocal()
    try:
        cid = chat_id
        if cid is None and role == "applicant":
            cid = f"chat_{uuid.uuid4().hex[:8]}"
        user = User(
            email=f"{role}_{uuid.uuid4().hex[:8]}@sdu.edu.kz",
            hashed_password=hash_password("Pass123!"),
            full_name=f"Sprint4 User {role.capitalize()}",
            role=role,
            is_active=True,
            is_verified=True,
            telegram_chat_id=cid,
            telegram_notifications_enabled=enabled,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        if cid:
            from app.models import TelegramBinding
            existing = db.query(TelegramBinding).filter(TelegramBinding.chat_id == cid).first()
            if existing:
                db.delete(existing)
                db.commit()
            db.add(TelegramBinding(user_id=user.id, chat_id=cid, verified_at=datetime.utcnow()))
            db.commit()
        token = create_access_token({"sub": str(user.id)})
        return user, token
    finally:
        db.close()

# ==============================================================================
# US8: DEADLINES & CALENDAR ACCEPTANCE & EDGE CASES
# ==============================================================================

def test_us8_calendar_boundary_validation_and_full_year():
    """Verify calendar endpoint handles out-of-bounds month and full-year retrieval."""
    # 1. Invalid month > 12 should return 422 Unprocessable Entity
    resp_invalid_month = client.get("/deadlines/calendar?year=2026&month=13")
    assert resp_invalid_month.status_code == 422

    resp_zero_month = client.get("/deadlines/calendar?year=2026&month=0")
    assert resp_zero_month.status_code == 422

    # 2. Year without month returns full campaign months (January to August)
    resp_full_year = client.get("/deadlines/calendar?year=2026")
    assert resp_full_year.status_code == 200
    data = resp_full_year.json()
    assert data["year"] == 2026
    assert len(data["months"]) >= 7  # Jan through Aug campaign months
    month_numbers = [m["month"] for m in data["months"]]
    assert 1 in month_numbers
    assert 7 in month_numbers
    assert 8 in month_numbers


def test_us8_kazakh_language_complex_queries():
    """Verify chatbot understands varied Kazakh questions regarding deadlines with special characters."""
    kazakh_queries = [
        "мемлекеттік грант мерзімі қашан",
        "құжат тапсыру мерзімі қашан",
        "жатақхана қабылдау мерзімдері",
        "дедлайн қашан",
    ]
    for q in kazakh_queries:
        res = chatbot.answer_query(q, language="kk")
        assert res["confident"] is True, f"Failed confidence for: {q}"
        assert res["source"] == "deadlines", f"Failed source routing for: {q}"
        # Response should contain localized Kazakh text
        assert ("SDU" in res["answer"]) or ("қабылдау" in res["answer"])


def test_us8_all_timeline_items_have_valid_schema_and_colors():
    """Verify all deadlines in master catalog satisfy complete schema and color mapping in calendar."""
    for lang in ("ru", "kk", "en"):
        deadlines = get_all_deadlines(lang=lang)
        assert len(deadlines) >= 8
        for dl in deadlines:
            assert dl["id"] != ""
            assert dl["title"] != ""
            assert dl["date_start"] != ""
            assert dl["date_end"] != ""
            assert isinstance(dl["days_left"], int)
            assert dl["status"] in ("active", "upcoming", "passed")
            assert dl["category"] in ("grant", "unt", "dormitory", "exam", "olympiad", "contract")
            assert dl["action_url"].startswith("http")

        # Calendar events must have color mapping
        cal = get_calendar_events(year=2026, month=7, lang=lang)
        for m in cal["months"]:
            for ev in m["events"]:
                assert ev["color"] in ("gold", "blue", "green", "purple", "red")


# ==============================================================================
# US13: FAQ ADMIN MANAGEMENT ACCEPTANCE & EDGE CASES
# ==============================================================================

def test_us13_faq_search_and_category_filtering():
    """Verify staff can search FAQs by substring and filter by category via API."""
    _, manager_token = _create_user(role="manager")
    headers = {"Authorization": f"Bearer {manager_token}"}

    unique_slug = f"stemclub_{uuid.uuid4().hex[:6]}"

    # Create 2 FAQs in different categories
    client.post("/admin/faqs", json={
        "question": f"How to join the {unique_slug} astronomy club?",
        "answer": "Sign up during orientation week in the student center.",
        "category": "clubs",
        "keywords": [unique_slug, "astronomy", "student center"],
    }, headers=headers)

    client.post("/admin/faqs", json={
        "question": f"Is tuition refundable for {unique_slug} courses?",
        "answer": "Tuition refunds follow the standard 14-day university policy.",
        "category": "tuition",
        "keywords": [unique_slug, "refund", "policy"],
    }, headers=headers)

    # 1. Search by slug query parameter
    search_res = client.get(f"/admin/faqs?search={unique_slug}", headers=headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data) == 2

    # 2. Filter by category='clubs'
    cat_res = client.get(f"/admin/faqs?search={unique_slug}&category=clubs", headers=headers)
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert len(cat_data) == 1
    assert cat_data[0]["category"] == "clubs"


def test_us13_faq_input_validation_boundaries():
    """Verify FAQ creation rejects short questions, empty answers, or invalid payloads."""
    _, admin_token = _create_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Too short question (< 3 chars)
    res_short_q = client.post("/admin/faqs", json={
        "question": "Hi",
        "answer": "Valid length answer text.",
        "category": "general",
    }, headers=headers)
    assert res_short_q.status_code == 422

    # Empty answer
    res_empty_a = client.post("/admin/faqs", json={
        "question": "Valid length question?",
        "answer": "",
        "category": "general",
    }, headers=headers)
    assert res_empty_a.status_code == 422


def test_us13_faq_delete_and_unmatch_in_chatbot():
    """Verify deleting an FAQ immediately purges it from live chatbot matching."""
    _, admin_token = _create_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    secret_key = f"quantumrobot_{uuid.uuid4().hex[:6]}"
    create_res = client.post("/admin/faqs", json={
        "question": f"Tell me about {secret_key}",
        "answer": f"The secret lab for {secret_key} is located underground.",
        "category": "general",
        "keywords": [secret_key],
    }, headers=headers)
    assert create_res.status_code == 201
    faq_id = create_res.json()["id"]

    # Before deletion: Chatbot answers with confidence
    before_resp = chatbot.answer_query(f"What is {secret_key}?")
    assert before_resp["confident"] is True
    assert "underground" in before_resp["answer"]

    # Delete FAQ
    del_res = client.delete(f"/admin/faqs/{faq_id}", headers=headers)
    assert del_res.status_code == 200

    # After deletion: Chatbot no longer answers this question
    after_resp = chatbot.answer_query(f"What is {secret_key}?")
    assert after_resp["confident"] is False
    assert after_resp["matched_id"] != faq_id


# ==============================================================================
# US20: TELEGRAM PUSH ALERTS ACCEPTANCE & EDGE CASES
# ==============================================================================

def test_us20_alert_html_message_formatting():
    """Verify alert message template formats HTML, urgency, days left, and action link properly."""
    deadline_mock = {
        "title": "SDU State Grant Competition",
        "date_start": "2026-07-13",
        "date_end": "2026-07-20",
        "days_left": 3,
        "description": "Annual state grant competition portal.",
        "action_url": "https://app.sdu.edu.kz",
        "category": "grant",
        "alert_type": "closing",
    }
    # 3-day alert formatting
    msg_3d = format_deadline_alert_html("Arman", deadline_mock, days_ahead=3)
    assert "Напоминание о дедлайне" in msg_3d
    assert "<b>Arman</b>" in msg_3d
    assert "SDU State Grant Competition" in msg_3d
    assert "3 дн." in msg_3d
    assert "https://app.sdu.edu.kz" in msg_3d

    # 1-day alert formatting
    msg_1d = format_deadline_alert_html("Amina", deadline_mock, days_ahead=1)
    assert "<b>Amina</b>" in msg_1d
    assert "1 дн." in msg_1d


def test_us20_quiet_hours_exact_edge_minutes():
    """Verify minute-by-minute edge cases for Almaty 22:00-08:00 quiet hours."""
    # 21:59 Almaty time -> NOT quiet hours (allowed to send)
    t_2159 = datetime(2026, 7, 10, 21, 59, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(t_2159) is False

    # 22:00 Almaty time -> QUIET HOURS starts (suppressed)
    t_2200 = datetime(2026, 7, 10, 22, 0, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(t_2200) is True

    # 07:59 Almaty time -> QUIET HOURS still active (suppressed)
    t_0759 = datetime(2026, 7, 10, 7, 59, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(t_0759) is True

    # 08:00 Almaty time -> QUIET HOURS ended (allowed to send)
    t_0800 = datetime(2026, 7, 10, 8, 0, tzinfo=ALMATY_TZ)
    assert is_almaty_quiet_hours(t_0800) is False


def test_us20_batch_alerts_multi_user_dispatch(monkeypatch):
    """Verify batch alert correctly delivers to active users and skips unverified/muted users."""
    user_active, _ = _create_user(chat_id="111222", enabled=True)
    user_muted, _ = _create_user(chat_id="333444", enabled=False)

    delivered_messages = []

    def mock_send_telegram(chat_id: str, text: str, **kwargs) -> bool:
        delivered_messages.append((chat_id, text))
        return True

    from app import telegram_service
    monkeypatch.setattr(telegram_service, "send_telegram_message", mock_send_telegram)
    monkeypatch.setattr(telegram_service, "is_telegram_configured", lambda: True)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://admissions.sdu.edu.kz")

    # Simulated reference date where July 20 deadline is exactly 3 days away (2026-07-17)
    # and daytime (14:00)
    ref_dt = datetime(2026, 7, 17, 14, 0, tzinfo=ALMATY_TZ)

    db = SessionLocal()
    try:
        res = send_deadline_alerts(db=db, target_days_ahead=3, force_send=True, reference_date=ref_dt)
        assert res["dispatched"] >= 1

        # Active user got message, muted user did NOT get message
        sent_chat_ids = [chat_id for chat_id, _ in delivered_messages]
        assert "111222" in sent_chat_ids
        assert "333444" not in sent_chat_ids
    finally:
        db.close()


def test_us20_admin_trigger_alerts_endpoint(monkeypatch):
    from app import telegram_service
    monkeypatch.setattr(telegram_service, "is_telegram_configured", lambda: True)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://admissions.sdu.edu.kz")
    """Verify admin /deadlines/trigger-alerts endpoint triggers manual dispatch with force flag."""
    _, admin_token = _create_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.post("/deadlines/trigger-alerts?days_ahead=3&force_send=true", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "dispatched" in data
    assert "deadlines_checked" in data
