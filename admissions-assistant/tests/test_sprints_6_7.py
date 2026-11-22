"""Acceptance checks for program choice, staff reporting and support conversations."""
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.db_session import SessionLocal
from app.main import app
from app.models import User, ChatSession, ChatMessage
from app.security import create_access_token

client = TestClient(app)


def account(role):
    with SessionLocal() as db:
        user = User(full_name="Test " + role, hashed_password="unused", role=role, is_verified=True)
        db.add(user)
        db.commit()
        return user.id, {"Authorization": "Bearer " + create_access_token({"sub": str(user.id)})}


@pytest.mark.parametrize("interest,goal,expected", [
    ("financial analysis", "financial analyst", "sdu-fin"),
    ("accounting", "auditor", "sdu-acc"),
    ("marketing campaigns", "marketing analyst", "sdu-mkt"),
    ("translation", "translator", "sdu-trans"),
    ("international law", "international legal adviser", "sdu-ilaw"),
])
def test_program_profiles(interest, goal, expected):
    result = client.post("/choices/recommend", json={"interests": interest, "background": "mathematics", "goals": goal})
    assert result.status_code == 200
    assert result.json()[0]["id"] == expected


@pytest.mark.parametrize("pid", ["sdu-is", "sdu-fin", "sdu-law", "sdu-acc", "sdu-mkt"])
def test_compare_and_missing_values(pid):
    result = client.get("/choices/compare", params=[("ids", "sdu-cs"), ("ids", pid)])
    assert [row["id"] for row in result.json()] == ["sdu-cs", pid]
    assert all({"annual_fee", "grants", "passing_score", "years"} <= row.keys() for row in result.json())
    assert result.json()[0]["grants"] == "State grant competition"
    assert client.get("/choices/compare", params={"ids": pid}).status_code == 422
    assert client.post("/choices/recommend", json={"interests": " "}).status_code == 422


@pytest.mark.parametrize("lang,word", [("en","Systems analyst"), ("ru","Системный аналитик"), ("kk","Жүйелік талдаушы")])
def test_career_chat_in_selected_language(lang, word):
    result = client.post("/chat", json={"message": "Career options for Information Systems?", "language": lang})
    assert word in result.json()["answer"]
    assert "https://sdu.edu.kz/" in result.json()["answer"]
    assert "85%" in client.get("/choices/sdu-cs/careers", params={"language": lang}).json()["statistics"]
    assert len(client.get("/choices/policy").json()["documents"]) >= 8


def test_officer_handoff_and_single_feedback():
    aid, applicant = account("applicant")
    _, other = account("applicant")
    _, manager = account("manager")
    _, second_officer = account("admin")
    sid = str(uuid4())
    with SessionLocal() as db:
        db.add(ChatSession(id=sid, user_id=aid, title="Document concession"))
        db.commit()
        db.add(ChatMessage(session_id=sid, sender="user", message="Please review this document."))
        db.commit()
    request = {"session_id": sid, "callback": "callback@example.test"}
    assert client.post("/handoff", headers=other, json=request).status_code == 404
    assert client.post("/handoff", headers=applicant, json=request).status_code == 200
    queue = client.get("/admin/consultations", headers=manager).json()
    assert any(item["session_id"] == sid and item["callback"] == request["callback"] for item in queue)
    assert client.post("/handoff", headers=applicant, json=request).json()["online"]
    assert client.get("/handoff/current", headers=applicant).json()["session_id"] == sid
    path = "/admin/consultations/" + sid
    assert client.post(path + "/claim", headers=manager).json()[0]["sender"] == "user"
    assert client.post(path + "/claim", headers=second_officer).status_code == 409
    assert client.post(path + "/messages", headers=manager, json={"message": "Welcome"}).status_code == 200
    assert client.get("/handoff/" + sid, headers=applicant).json()[-1]["message"] == "Welcome"
    assert client.get("/handoff/" + sid, headers=other).status_code == 404
    assert client.delete(path, headers=manager).status_code == 200
    assert client.get("/handoff/" + sid, headers=applicant).status_code == 410
    rating = {"score": 2, "session_id": sid}
    assert client.post("/feedback", headers=applicant, json=rating).status_code == 201
    assert client.post("/feedback", headers=applicant, json=rating).status_code == 409
    assert client.get("/admin/feedback", headers=other).status_code == 403
    review = client.get("/admin/feedback", headers=manager).json()["review"]
    assert any(r["session_id"] == sid and r["transcript"][-1]["sender"] == "operator" for r in review)


def test_staff_excel_export():
    _, manager = account("manager")
    _, applicant = account("applicant")
    with SessionLocal() as db:
        db.add_all([User(full_name=f"=Audit{i}", hashed_password="unused", role="applicant") for i in range(101)])
        db.commit()
    path = "/admin/reports/applicants.xlsx"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=applicant).status_code == 403
    response = client.get(path, headers=manager)
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet.max_row >= 102
    assert sheet["A1"].value == "Name"
    assert all(row[0].data_type == "s" for row in sheet.iter_rows(min_row=2))
    filtered = client.get(path, headers=manager, params={"end":"1990-01-01"})
    assert load_workbook(BytesIO(filtered.content)).active.max_row == 1
    popularity = client.get("/admin/reports/programs.xlsx", headers=manager)
    summary = load_workbook(BytesIO(popularity.content)).active
    assert summary.cell(summary.max_row, 1).value == "Total"
