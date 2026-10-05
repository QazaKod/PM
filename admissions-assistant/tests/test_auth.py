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
        "confirm_password": TEST_PASSWORD,
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


def test_register_password_mismatch():
    payload = {
        "email": f"mismatch_{uuid.uuid4().hex[:6]}@sdu.edu.kz",
        "password": "Password123!",
        "confirm_password": "DifferentPassword456!",
        "full_name": "Aslan Bolatov"
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert "Passwords do not match" in response.text


def test_register_invalid_email():
    payload = {
        "email": "not-an-email-address",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Aslan Bolatov"
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert "Invalid email" in response.text


def test_register_duplicate_email():
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
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


def test_update_profile_valid_phone():
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
        "phone": "+7 (777) 123-45-67"
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
    assert data["phone"] == "+7 (777) 123-45-67"


def test_update_profile_invalid_phone():
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    token = login_resp.json()["access_token"]

    # Less than 10 digits
    update_payload = {
        "phone": "12345"
    }
    response = client.put(
        "/auth/profile",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422
    assert "Phone number must contain between 10 and 15 digits" in response.text


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
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set profile to domestic + undergraduate
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
    assert data["source"] == "requirements"
    assert "session_id" in data
    assert data["session_id"] is not None


def test_forgot_and_reset_password_flow():
    # 1. Request forgot password
    forgot_resp = client.post("/auth/forgot-password", json={"email": TEST_EMAIL})
    assert forgot_resp.status_code == 200
    data = forgot_resp.json()
    assert data["status"] == "ok"
    assert "debug_code" in data
    code = data["debug_code"]

    # 2. Try resetting with mismatched passwords (should fail)
    mismatch_resp = client.post("/auth/reset-password", json={
        "email": TEST_EMAIL,
        "code": code,
        "new_password": "NewSecretPassword123!",
        "confirm_password": "DifferentPassword!"
    })
    assert mismatch_resp.status_code == 422

    # 3. Try resetting with invalid code (should fail)
    bad_code_resp = client.post("/auth/reset-password", json={
        "email": TEST_EMAIL,
        "code": "000000",
        "new_password": "NewSecretPassword123!",
        "confirm_password": "NewSecretPassword123!"
    })
    assert bad_code_resp.status_code == 400

    # 4. Reset with valid code and matching passwords
    reset_resp = client.post("/auth/reset-password", json={
        "email": TEST_EMAIL,
        "code": code,
        "new_password": "NewSecretPassword123!",
        "confirm_password": "NewSecretPassword123!"
    })
    assert reset_resp.status_code == 200
    assert "successfully reset" in reset_resp.json()["message"]

    # 5. Old password should now fail
    old_login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert old_login_resp.status_code == 401

    # 6. New password should successfully log in
    new_login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": "NewSecretPassword123!"
    })
    assert new_login_resp.status_code == 200
    assert "access_token" in new_login_resp.json()


def test_telegram_password_reset_and_webhook():
    # 1. Request reset via Telegram channel
    tg_forgot_resp = client.post("/auth/forgot-password", json={
        "email": TEST_EMAIL,
        "channel": "telegram"
    })
    assert tg_forgot_resp.status_code == 200
    data = tg_forgot_resp.json()
    assert data["status"] == "ok"
    assert data["channel"] == "telegram"
    assert "bot_url" in data
    code = data["debug_code"]
    assert code is not None

    # 2. Simulate user sending /start reset_<CODE> in Telegram Bot (Webhook)
    webhook_payload = {
        "update_id": 99999,
        "message": {
            "message_id": 1,
            "from": {"id": 12345678, "first_name": "Aslan", "username": "aslan_sdu"},
            "chat": {"id": 12345678, "type": "private"},
            "date": 1728000000,
            "text": f"/start reset_{code}"
        }
    }
    webhook_resp = client.post("/auth/telegram-webhook", json=webhook_payload)
    assert webhook_resp.status_code == 200
    res_data = webhook_resp.json()
    assert res_data["ok"] is True
    assert res_data["result"]["action"] == "reset_code_delivered"

    # 3. Reset password using the verified code
    reset_resp = client.post("/auth/reset-password", json={
        "email": TEST_EMAIL,
        "code": code,
        "new_password": "TelegramPassword999!",
        "confirm_password": "TelegramPassword999!"
    })
    assert reset_resp.status_code == 200

    # 4. Login with newly set password
    login_resp = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": "TelegramPassword999!"
    })
    assert login_resp.status_code == 200
    # Also verify that the user's telegram_chat_id is linked
    user_me = client.get("/auth/me", headers={"Authorization": f"Bearer {login_resp.json()['access_token']}"})
    assert user_me.status_code == 200
    assert user_me.json()["telegram_chat_id"] == "12345678"
    assert user_me.json()["telegram_username"] == "aslan_sdu"


