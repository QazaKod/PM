"""Acceptance scenarios for US6 analytics and US23 announcements."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db_session import get_db
from app.main import app
from app.models import ApplicantProfile, Base, ChatSession, Program, SavedProgram, User
from app.security import create_access_token


@pytest.fixture
def staff_portal(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def get_portal_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, get_portal_db)
    with Session(engine) as db:
        staff = [
            User(full_name="Test Manager", role="manager", hashed_password="unused"),
            User(full_name="Test Admin", role="admin", hashed_password="unused"),
        ]
        db.add_all(staff)
        db.commit()
        headers = {user.role: auth_header(user) for user in staff}
    try:
        with TestClient(app) as client:
            yield client, engine, headers
    finally:
        engine.dispose()


def auth_header(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


def test_us6_empty_dashboard_and_role_permissions(staff_portal):
    client, engine, headers = staff_portal
    path = "/admin/analytics"
    assert client.get(path).status_code == 401
    zero = {
        "total_applicants": 0,
        "domestic_applicants": 0,
        "international_applicants": 0,
        "unspecified_applicants": 0,
        "total_chat_sessions": 0,
        "top_saved_programs": [],
    }
    for staff in headers.values():
        result = client.get(path, headers=staff)
        assert result.status_code == 200
        assert result.headers["Cache-Control"] == "no-store"
        assert result.json() == zero
    with Session(engine) as db:
        applicant = User(full_name="Test Applicant", role="applicant", hashed_password="unused")
        db.add(applicant)
        db.commit()
        applicant_headers = auth_header(applicant)
    denied = client.get(path, headers=applicant_headers)
    assert denied.status_code == 403
    assert set(denied.json()) == {"detail"}


def test_us6_counts_and_ranks_real_records(staff_portal):
    client, engine, headers = staff_portal
    with Session(engine) as db:
        domestic = User(full_name="Domestic", hashed_password="unused", profile=ApplicantProfile(citizenship="domestic"))
        international = User(full_name="International", hashed_password="unused", profile=ApplicantProfile(citizenship="international"))
        unspecified = User(full_name="Unspecified", hashed_password="unused")
        manager = db.query(User).filter_by(role="manager").one()
        cs = Program(id="analytics-cs", name="Computer Science")
        law = Program(id="analytics-law", name="Law")
        finance = Program(id="analytics-finance", name="Finance")
        db.add_all([
            domestic, international, unspecified,
            ChatSession(user=domestic), ChatSession(user=international), ChatSession(),
            SavedProgram(user=domestic, program=cs), SavedProgram(user=international, program=cs),
            SavedProgram(user=international, program=cs),
            SavedProgram(user=international, program=law),
            SavedProgram(user=domestic, program=finance),
            SavedProgram(user=manager, program=law),
        ])
        db.commit()
    result = client.get("/admin/analytics", headers=headers["manager"])
    assert result.status_code == 200
    assert result.json() == {
        "total_applicants": 3,
        "domestic_applicants": 1,
        "international_applicants": 1,
        "unspecified_applicants": 1,
        "total_chat_sessions": 3,
        "top_saved_programs": [
            {"program_id": "analytics-cs", "name": "Computer Science", "saved_count": 2},
            {"program_id": "analytics-finance", "name": "Finance", "saved_count": 1},
            {"program_id": "analytics-law", "name": "Law", "saved_count": 1},
        ],
    }


def test_us23_publish_edit_deactivate_and_delete(staff_portal):
    client, _, headers = staff_portal
    public_path = "/announcements"
    staff_path = "/admin/announcements"
    manager, admin = headers["manager"], headers["admin"]
    content = {
        "title": "Open House",
        "message": "Meet the admissions team on Saturday.",
        "category": "event",
        "link": "https://example.org/open-house",
    }
    assert client.get(public_path).json() == []
    created = client.post(staff_path, json={**content, "is_active": True}, headers=manager)
    assert created.status_code == 201
    notice = created.json()
    assert notice["is_active"] is True
    notice_path = f"{staff_path}/{notice['id']}"
    public = client.get(public_path)
    assert public.headers["Cache-Control"] == "no-store"
    assert public.json() == [{"id": notice["id"], **content}]

    edited = {**content, "message": "Meet the team on Friday.", "link": None}
    edit = client.put(notice_path, json=edited, headers=admin)
    assert edit.status_code == 200
    assert edit.json()["is_active"] is True
    assert client.get(public_path).json() == [{"id": notice["id"], **edited}]

    for _ in range(2):
        deactivate = client.patch(f"{notice_path}/status", json={"is_active": False}, headers=manager)
        assert deactivate.status_code == 200
        assert deactivate.json()["is_active"] is False
    assert client.get(public_path).json() == []
    assert client.get(staff_path, headers=manager).json() == [deactivate.json()]

    assert client.patch(f"{notice_path}/status", json={"is_active": True}, headers=admin).status_code == 200
    assert len(client.get(public_path).json()) == 1
    assert client.delete(notice_path, headers=admin).status_code == 204
    assert client.get(staff_path, headers=manager).json() == []
    assert client.get(public_path).json() == []
    assert client.patch(f"{notice_path}/status", json={"is_active": True}, headers=admin).status_code == 404


def test_us23_staff_only_and_validated_input(staff_portal):
    client, engine, headers = staff_portal
    with Session(engine) as db:
        applicant = User(full_name="Test Applicant", hashed_password="unused")
        db.add(applicant)
        db.commit()
        applicant_headers = auth_header(applicant)

    path = "/admin/announcements"
    valid = {"title": "Registration", "message": "Registration opens tomorrow."}
    for actor, expected_status in [({}, 401), (applicant_headers, 403)]:
        for method, suffix, payload in [
            ("GET", "", None),
            ("POST", "", valid),
            ("PUT", "/1", valid),
            ("PATCH", "/1/status", {"is_active": True}),
            ("DELETE", "/1", None),
        ]:
            response = client.request(method, path + suffix, json=payload, headers=actor)
            assert response.status_code == expected_status

    manager = headers["manager"]
    for invalid in [
        {"title": " "},
        {"message": "\n "},
        {"message": "x" * 501},
        {"category": "custom"},
        {"link": "javascript:alert(1)"},
    ]:
        assert client.post(path, json={**valid, **invalid}, headers=manager).status_code == 422
    assert client.get(path, headers=manager).json() == []
    draft = client.post(path, json=valid, headers=manager)
    assert draft.status_code == 201
    assert draft.json()["is_active"] is False
    assert client.get("/announcements", headers=applicant_headers).json() == []
