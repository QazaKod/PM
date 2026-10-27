"""US8: Deadlines & Academic Calendar Test Suite."""

from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.services.deadlines import (
    get_all_deadlines,
    get_calendar_events,
    get_upcoming_deadlines_for_alert,
    compute_status_and_days_left,
)
from app import chatbot


client = TestClient(app)


def test_get_all_deadlines_structure():
    """Verify all 8+ official admissions campaign deadlines are returned with required fields."""
    deadlines = get_all_deadlines()
    assert len(deadlines) >= 8

    required_fields = {
        "id", "title", "stage_name", "date_start", "date_end",
        "category", "degree_level", "status", "days_left",
        "description", "action_url", "passed_advice",
    }
    for item in deadlines:
        assert required_fields.issubset(set(item.keys()))
        assert item["status"] in ("active", "upcoming", "passed")
        assert item["days_left"] >= 0
        assert item["action_url"].startswith("http")


def test_category_and_degree_filtering():
    """Verify filtering by category and degree level."""
    grant_deadlines = get_all_deadlines(category="grant")
    assert len(grant_deadlines) >= 2
    for item in grant_deadlines:
        assert item["category"] == "grant"

    unt_deadlines = get_all_deadlines(category="unt")
    assert len(unt_deadlines) >= 2
    for item in unt_deadlines:
        assert item["category"] == "unt"

    dorm_deadlines = get_all_deadlines(category="dormitory")
    assert len(dorm_deadlines) >= 1
    for item in dorm_deadlines:
        assert item["category"] == "dormitory"

    undergrad = get_all_deadlines(degree_level="undergraduate")
    for item in undergrad:
        assert item["degree_level"] in ("undergraduate", "all")


def test_multilingual_localization():
    """Verify localized output for RU, KK, and EN."""
    ru_items = get_all_deadlines(lang="ru")
    kk_items = get_all_deadlines(lang="kk")
    en_items = get_all_deadlines(lang="en")

    assert len(ru_items) == len(kk_items) == len(en_items)

    grant_ru = next(x for x in ru_items if x["id"] == "state_grant_competition")
    grant_kk = next(x for x in kk_items if x["id"] == "state_grant_competition")
    grant_en = next(x for x in en_items if x["id"] == "state_grant_competition")

    assert "грант" in grant_ru["title"].lower()
    assert "грант" in grant_kk["title"].lower()
    assert "grant" in grant_en["title"].lower()


def test_dynamic_status_computation():
    """Verify active, upcoming, and passed status logic based on reference date."""
    d_start = date(2026, 7, 13)
    d_end = date(2026, 7, 20)

    # Before start -> upcoming
    status, days = compute_status_and_days_left(d_start, d_end, date(2026, 7, 10))
    assert status == "upcoming"
    assert days == 10

    # During stage -> active
    status, days = compute_status_and_days_left(d_start, d_end, date(2026, 7, 15))
    assert status == "active"
    assert days == 5

    # Exactly on deadline end -> active with 0 days left
    status, days = compute_status_and_days_left(d_start, d_end, date(2026, 7, 20))
    assert status == "active"
    assert days == 0

    # Past deadline -> passed
    status, days = compute_status_and_days_left(d_start, d_end, date(2026, 7, 21))
    assert status == "passed"
    assert days == 0


def test_calendar_grid_events():
    """Verify calendar events grouped by month with colors and daily arrays."""
    cal = get_calendar_events(year=2026, month=7)
    assert cal["year"] == 2026
    assert len(cal["months"]) == 1

    july = cal["months"][0]
    assert july["month"] == 7
    assert len(july["events"]) >= 1

    # Check color coding
    colors_found = {ev["color"] for ev in july["events"]}
    assert any(c in colors_found for c in ("gold", "blue", "red", "green", "purple"))

    # Day 15 should have active events (State Grant Competition, Creative Exams, etc.)
    assert 15 in july["days"]
    assert len(july["days"][15]) >= 1


def test_upcoming_deadlines_for_alert():
    """Verify alert filtering for deadlines exactly days_ahead days away."""
    # State grant competition starts 2026-07-13. 3 days before is 2026-07-10.
    alerts_start = get_upcoming_deadlines_for_alert(days_ahead=3, reference_date=date(2026, 7, 10))
    assert any(a["id"] == "state_grant_competition" for a in alerts_start)

    # State grant competition ends 2026-07-20. 3 days before is 2026-07-17.
    alerts_end = get_upcoming_deadlines_for_alert(days_ahead=3, reference_date=date(2026, 7, 17))
    assert any(a["id"] == "state_grant_competition" for a in alerts_end)


def test_api_deadlines_endpoints():
    """Verify /deadlines and /deadlines/calendar API endpoints."""
    # List deadlines
    res = client.get("/deadlines?lang=ru")
    assert res.status_code == 200
    data = res.json()
    assert "deadlines" in data
    assert data["total"] >= 8

    # Filtered
    res_grant = client.get("/deadlines?category=grant")
    assert res_grant.status_code == 200
    assert res_grant.json()["total"] >= 2

    # Calendar
    res_cal = client.get("/deadlines/calendar?year=2026&month=7")
    assert res_cal.status_code == 200
    cal_data = res_cal.json()
    assert cal_data["year"] == 2026
    assert len(cal_data["months"]) == 1


def test_chatbot_deadline_intent_routing():
    """Verify chatbot routes deadline-related questions to source='deadlines'."""
    queries = [
        "какой дедлайн на грант",
        "до какого числа прием документов",
        "application deadline for bachelor",
        "грант мерзімі қашан",
        "дедлайн общежития",
        "когда заканчивается прием документов",
    ]
    for q in queries:
        resp = chatbot.answer_query(q)
        assert resp["source"] == "deadlines", f"Failed for query: {q}"
        assert resp["confident"] is True
        assert "SDU" in resp["answer"]


def test_us8_scenario1_successful_deadline_query_all_degrees_categories_languages():
    """US8 Scenario 1: Successful deadline query via API and chatbot (all degree levels, categories, languages)."""
    # 1. API: Degree levels, categories, languages
    for degree in ("undergraduate", "graduate"):
        for cat in ("grant", "unt", "dormitory", "contract"):
            for lang in ("ru", "kk", "en"):
                res = client.get(f"/deadlines?category={cat}&degree_level={degree}&lang={lang}")
                assert res.status_code == 200
                payload = res.json()
                assert "deadlines" in payload
                assert "total" in payload

    # 2. Chatbot: Multilingual queries across degrees and categories
    chat_queries = [
        ("дедлайн на грант бакалавриат", "deadlines", "ru"),
        ("магистратура қабылдау мерзімі қашан", "deadlines", "kk"),
        ("dormitory application deadline for bachelor", "deadlines", "en"),
        ("платное отделение дедлайн приема документов", "deadlines", "ru"),
    ]
    for query_text, expected_src, _ in chat_queries:
        resp = chatbot.answer_query(query_text)
        assert resp["source"] == expected_src
        assert resp["confident"] is True
        assert len(resp["answer"]) > 50


def test_us8_scenario2_past_deadline_informs_user_and_suggests_alternative_advice():
    """US8 Scenario 2: Past deadline query informs user and suggests alternative actions/advice."""
    # Given an inquiry about a deadline milestone that has passed (e.g. SDU SPT Olympiad)
    resp = chatbot.answer_query("дедлайн олимпиады spt")
    assert resp["source"] == "deadlines"
    assert resp["confident"] is True
    # Informs the user that deadline has passed
    assert ("Срок завершен" in resp["answer"]) or ("Closed / Passed" in resp["answer"])
    # Suggests alternative advice (state grant, UNT high score discounts, etc.)
    assert "💡" in resp["answer"]
    assert ("государственный грант" in resp["answer"]) or ("скидки" in resp["answer"])

    # Directly verify service output with a simulated past date (e.g. 2026-09-01)
    past_deadlines = get_all_deadlines(lang="ru", reference_date=date(2026, 9, 1))
    for dl in past_deadlines:
        assert dl["status"] == "passed"
        assert dl["passed_advice"] != ""
        assert len(dl["passed_advice"]) > 10


def test_us8_calendar_grid_and_color_mapping():
    """US8 Calendar endpoint: monthly grid representation with active daily events and color mapping."""
    res = client.get("/deadlines/calendar?year=2026&month=7&lang=ru")
    assert res.status_code == 200
    cal_data = res.json()
    assert cal_data["year"] == 2026
    assert len(cal_data["months"]) == 1

    month_obj = cal_data["months"][0]
    assert month_obj["month"] == 7
    assert month_obj["month_name"] == "Июль"

    # Monthly events must have valid category color mapping
    assert len(month_obj["events"]) >= 1
    valid_colors = {"gold", "blue", "green", "purple", "red"}
    for ev in month_obj["events"]:
        assert ev["color"] in valid_colors
        assert ev["action_url"].startswith("http")

    # Day arrays must contain active events for those dates
    # July 15 is within State Grant Competition (July 13 - 20)
    day15_events = month_obj["days"]["15"]
    assert len(day15_events) >= 1
    assert any(ev["category"] == "grant" and ev["color"] == "gold" for ev in day15_events)

