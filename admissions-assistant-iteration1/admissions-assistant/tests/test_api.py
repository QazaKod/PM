"""API Integration tests for FastAPI endpoints:
- GET /health
- GET /programs (US1)
- GET /faq (US5)
- GET / (Root SPA index.html)
- POST /chat (Unified assistant)
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_programs_endpoint():
    response = client.get("/programs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 4
    # Check that known programs are present
    program_ids = [p["id"] for p in data]
    assert "cs-bachelor" in program_ids
    assert "it-bachelor" in program_ids


def test_get_faq_endpoint():
    response = client.get("/faq")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    faq_ids = [item["id"] for item in data]
    assert "faq-1" in faq_ids


def test_post_chat_unified():
    response = client.post("/chat", json={"message": "How much does Computer Science cost?"})
    assert response.status_code == 200
    data = response.json()
    assert data["confident"] is True
    assert data["source"] == "program"
    assert "Computer Science" in data["answer"]


def test_get_root_serves_spa():
    response = client.get("/")
    assert response.status_code == 200
    assert "Smart University Admissions Assistant" in response.text
    assert "id=\"sidebar\"" in response.text
    assert "id=\"section-chat\"" in response.text
