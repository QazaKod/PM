"""
Tests for Phase 1, Phase 2, and Phase 3 Remediation Plan:
- P0 Security: JWT secret enforcement, debug_code leak prevention, 5-attempt brute-force lockout, sliding-window rate limiting
- P1 Infrastructure: SQLite WAL mode & postgres:// URL normalization, async BackgroundTasks delivery
- P2 AI & Frontend: Stem/synonym matching, multi-turn conversation history, dynamic /admissions/metadata catalog
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import get_jwt_secret_key
from app.rate_limit import rate_limiter
from app import chatbot

client = TestClient(app)


# ==========================================
# PHASE 1: P0 SECURITY TESTS
# ==========================================

def test_jwt_secret_raises_in_production_when_unset(monkeypatch):
    """Ensure production startup fails fast if JWT_SECRET_KEY is missing."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_jwt_secret_key()


def test_jwt_secret_never_uses_static_hardcoded_fallback(monkeypatch):
    """Ensure unset JWT_SECRET_KEY in dev generates a unique random key, never a static repo string."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("ENV", "development")
    key1 = get_jwt_secret_key()
    key2 = get_jwt_secret_key()
    assert key1 != "sdu-admissions-super-secret-key-change-in-prod-2026"
    assert len(key1) == 64
    assert key1 != key2


def test_debug_code_not_leaked_outside_test_mode(monkeypatch):
    """Verify debug_code is never returned when TESTING is false, even if DEBUG=true."""
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setenv("DEBUG", "true")

    email = f"noleak_{uuid.uuid4().hex[:8]}@sdu.edu.kz"
    resp = client.post("/auth/register", json={
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "No Leak User",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("debug_code") is None


def test_verify_registration_brute_force_lockout():
    """Verify that 5 wrong verification code attempts invalidate the code and return HTTP 429."""
    email = f"bruteforce_{uuid.uuid4().hex[:8]}@sdu.edu.kz"
    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Brute Force Target",
    })
    assert reg_resp.status_code == 200
    real_code = reg_resp.json()["debug_code"]
    wrong_code = "000000" if real_code != "000000" else "999999"

    # Attempts 1..4 return 400 Bad Request
    for _ in range(4):
        r = client.post("/auth/verify-registration", json={
            "identifier": email,
            "code": wrong_code,
        })
        assert r.status_code == 400

    # Attempt 5 triggers lockout -> 429 Too Many Requests
    r5 = client.post("/auth/verify-registration", json={
        "identifier": email,
        "code": wrong_code,
    })
    assert r5.status_code == 429
    assert "invalidated" in r5.json()["detail"].lower()

    # Even the real code must now be rejected because the token was invalidated
    r_after = client.post("/auth/verify-registration", json={
        "identifier": email,
        "code": real_code,
    })
    assert r_after.status_code in (400, 429)


def test_reset_password_brute_force_lockout():
    """Verify that 5 wrong password reset code attempts invalidate the reset token and return HTTP 429."""
    email = f"resetlock_{uuid.uuid4().hex[:8]}@sdu.edu.kz"
    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Reset Lock User",
    })
    code = reg_resp.json()["debug_code"]
    client.post("/auth/verify-registration", json={"identifier": email, "code": code})

    fp_resp = client.post("/auth/forgot-password", json={"email": email, "channel": "email"})
    assert fp_resp.status_code == 200
    reset_code = fp_resp.json()["debug_code"]
    wrong_code = "000000" if reset_code != "000000" else "999999"

    for _ in range(4):
        r = client.post("/auth/reset-password", json={
            "email": email,
            "code": wrong_code,
            "new_password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
        })
        assert r.status_code == 400

    r5 = client.post("/auth/reset-password", json={
        "email": email,
        "code": wrong_code,
        "new_password": "NewPassword123!",
        "confirm_password": "NewPassword123!",
    })
    assert r5.status_code == 429


def test_endpoint_rate_limiting_enforced(monkeypatch):
    """Verify sliding-window rate limiter blocks excessive requests with HTTP 429 and Retry-After header."""
    rate_limiter.reset()
    monkeypatch.setenv("ENABLE_RATE_LIMIT_IN_TESTS", "1")
    try:
        for _ in range(5):
            resp = client.post("/auth/forgot-password", json={
                "email": "nonexistent@sdu.edu.kz",
                "channel": "email",
            })
            assert resp.status_code == 200

        # 6th request within 60s window exceeds max_requests=5
        blocked = client.post("/auth/forgot-password", json={
            "email": "nonexistent@sdu.edu.kz",
            "channel": "email",
        })
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
    finally:
        rate_limiter.reset()


# ==========================================
# PHASE 2 & 3: AI RAG, MULTI-TURN & METADATA
# ==========================================

def test_chatbot_synonym_and_stem_matching():
    """Verify colloquial synonyms ('общага', 'доки') match FAQ entries accurately."""
    dorm_res = chatbot.answer_query("Есть ли общага для студентов?")
    assert dorm_res["confident"] is True
    assert dorm_res["source"] == "faq"
    assert dorm_res["matched_id"] == "faq_dorm"

    doc_res = chatbot.answer_query("Какие доки нужны для поступления?")
    assert doc_res["confident"] is True
    assert doc_res["source"] == "faq"
    assert doc_res["matched_id"] == "faq_documents"


def test_chatbot_multi_turn_history_followup():
    """Verify follow-up questions ('А какая стоимость туда?') resolve the program from conversation history."""
    history = [
        {"sender": "user", "message": "Tell me about the Finance program"},
        {"sender": "bot", "message": "**Finance** (6B04102) - Business School"},
    ]
    followup = chatbot.answer_query("А сколько стоит обучение туда?", history=history)
    assert followup["confident"] is True
    assert followup["source"] == "program"
    assert followup["matched_id"] == "sdu-fin"


def test_admissions_metadata_catalog_endpoint():
    """Verify GET /admissions/metadata returns live programs and UNT subjects from DB."""
    resp = client.get("/admissions/metadata")
    assert resp.status_code == 200
    data = resp.json()
    assert "programs" in data
    assert "unt_subjects" in data
    assert len(data["programs"]) >= 10
    assert any(p["id"] == "sdu-cs" for p in data["programs"])
    assert any(s["value"] == "Mathematics" for s in data["unt_subjects"])
