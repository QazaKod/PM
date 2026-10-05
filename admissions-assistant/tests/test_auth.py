import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TEST_EMAIL = f"applicant_{uuid.uuid4().hex[:8]}@sdu.edu.kz"
TEST_PASSWORD = "Password123!"


def test_register_applicant_success():
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": "Aslan Bolatov"
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == TEST_EMAIL
    assert data["user"]["role"] == "applicant"
    assert data["user"]["profile"]["citizenship"] == "domestic"


def test_register_duplicate_email():
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": "Aslan Bolatov"
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success():
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == TEST_EMAIL


def test_login_invalid_password():
    payload = {
        "email": TEST_EMAIL,
        "password": "WrongPassword!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401


def test_get_me_unauthorized():
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_me_authorized():
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    token = login_resp.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert data["profile"]["target_degree"] == "undergraduate"


def test_update_profile():
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    token = login_resp.json()["access_token"]

    update_payload = {
        "citizenship": "international",
        "target_degree": "graduate",
        "unt_score": 115,
        "ielts_score": 7.5,
        "phone": "+7 777 123 4567"
    }
    response = client.put(
        "/auth/profile",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["citizenship"] == "international"
    assert data["target_degree"] == "graduate"
    assert data["ielts_score"] == 7.5


def test_favorites_workflow():
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add favorite
    add_resp = client.post("/auth/favorites/sdu-cs", headers=headers)
    assert add_resp.status_code == 200
    assert add_resp.json()["program_id"] == "sdu-cs"

    # List favorites
    list_resp = client.get("/auth/favorites", headers=headers)
    assert list_resp.status_code == 200
    fav_ids = [f["program_id"] for f in list_resp.json()]
    assert "sdu-cs" in fav_ids

    # Remove favorite
    del_resp = client.delete("/auth/favorites/sdu-cs", headers=headers)
    assert del_resp.status_code == 200


def test_admin_panel_requires_login():
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in [302, 303, 401]


def test_personalized_chat_auto_fills_profile():
    # Login user
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Reset profile to domestic + undergraduate
    client.put("/auth/profile", json={
        "citizenship": "domestic",
        "target_degree": "undergraduate"
    }, headers=headers)

    # Ask requirements for Computer Science
    chat_resp = client.post(
        "/chat",
        json={"message": "What are the admission requirements for Computer Science?"},
        headers=headers
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    # Notice that because profile provides both domestic and undergraduate,
    # the requirements logic doesn't have to ask "domestic or international?" or "undergraduate or graduate?".
    # It immediately answers with the verified requirements!
    assert data["source"] == "requirements"
    assert "session_id" in data
    assert data["session_id"] is not None

