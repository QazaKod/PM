"""
Comprehensive QA & Security Integration Tests for Telegram Bot Registration,
Phone Validation, Contact Ownership Verification, 1-to-1 Account Binding,
Password Reset Hijack Prevention, and Profile Phone Synchronization.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db_session import SessionLocal
from app.models import (
    User,
    ApplicantProfile,
    AccountVerificationToken,
    PasswordResetToken,
)
from app.schemas import normalize_and_validate_phone
from app.telegram_service import process_telegram_update

client = TestClient(app)

TEST_PHONES = {
    "+77012345678",
    "77012345678",
    "+77029876543",
    "77029876543",
    "+77058889900",
    "77058889900",
}
TEST_EMAILS = {
    "77012345678@phone.sdu.edu.kz",
    "77029876543@phone.sdu.edu.kz",
    "77058889900@phone.sdu.edu.kz",
}
TEST_CHAT_IDS = {
    "555001",
    "555002",
    "555003",
    "555004",
    "777001",
    "888001",
    "999999",
}


def _purge_test_records() -> None:
    """Clean up test users and tokens created by this module so each test is isolated."""
    with SessionLocal() as db:
        users = (
            db.query(User)
            .filter(
                (User.phone.in_(TEST_PHONES))
                | (User.email.in_(TEST_EMAILS))
                | (User.telegram_chat_id.in_(TEST_CHAT_IDS))
            )
            .all()
        )
        user_ids = [u.id for u in users]
        if user_ids:
            db.query(AccountVerificationToken).filter(
                AccountVerificationToken.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(ApplicantProfile).filter(
                ApplicantProfile.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()


@pytest.fixture(autouse=True)
def isolated_telegram_test_state():
    _purge_test_records()
    yield
    _purge_test_records()


# ==============================================================================
# 1. PHONE NUMBER VALIDATION & NORMALIZATION
# ==============================================================================

def test_reject_fake_and_repeated_phone_numbers():
    """
    Reject fake, repeated-digit, sequential, and invalid Kazakhstan prefix phone numbers
    at registration with HTTP 422.
    """
    invalid_phones = [
        "77777777777",
        "+77777777777",
        "87777777777",
        "+77011111111",
        "+77011234567",
        "+77991234567",  # Invalid KZ operator prefix 799
    ]
    for bad_phone in invalid_phones:
        resp = client.post(
            "/auth/register",
            json={
                "full_name": "Fake Phone Tester",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "channel": "phone_telegram",
                "phone": bad_phone,
            },
        )
        assert resp.status_code == 422, f"Expected 422 for fake phone {bad_phone}, got {resp.status_code}"


def test_normalize_valid_kz_phone_variants():
    """Verify valid Kazakhstan phone formats normalize cleanly to canonical E.164 (+7...)."""
    assert normalize_and_validate_phone("87012345678") == "+77012345678"
    assert normalize_and_validate_phone("77012345678") == "+77012345678"
    assert normalize_and_validate_phone("+7 (701) 234-56-78") == "+77012345678"


# ==============================================================================
# 2. OPAQUE SESSION TOKEN & DEEP LINK SECURITY
# ==============================================================================

def test_bot_url_uses_opaque_session_token_never_exposes_6_digit_code():
    """
    Ensure /auth/register generates a 32-character hex session_token for the Telegram
    deep link (?start=verify_<session_token>) and NEVER embeds the 6-digit code in bot_url.
    """
    resp = client.post(
        "/auth/register",
        json={
            "full_name": "Timur Applicant",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    bot_url = data["bot_url"]
    session_token = data["session_token"]

    assert session_token is not None
    assert len(session_token) == 32
    assert f"?start=verify_{session_token}" in bot_url

    with SessionLocal() as db:
        token_rec = (
            db.query(AccountVerificationToken)
            .filter(AccountVerificationToken.session_token == session_token)
            .first()
        )
        assert token_rec is not None
        assert len(token_rec.code) == 6
        assert token_rec.code.isdigit()
        assert token_rec.code not in bot_url


# ==============================================================================
# 3. TWO-STEP TELEGRAM CONTACT SHARING & OWNERSHIP VERIFICATION
# ==============================================================================

def test_two_step_telegram_contact_verification_success(monkeypatch):
    """
    Full 2-step Telegram verification flow:
    1. Register with +77012345678
    2. /start verify_<session_token> -> requests contact, does NOT verify yet
    3. Premature POST /auth/verify-registration -> rejected with HTTP 400
    4. Share matching Telegram contact -> marks telegram_verified=True and delivers code
    5. Complete POST /auth/verify-registration -> activates user and syncs profile.phone
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    reg_resp = client.post(
        "/auth/register",
        json={
            "full_name": "Timur Satybaldin",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    session_token = reg_data["session_token"]
    code = reg_data["debug_code"]

    # Poll verification status before bot interaction
    status_before = client.get("/auth/verification-status", params={"identifier": "+77012345678"})
    assert status_before.status_code == 200
    assert status_before.json()["telegram_verified"] is False

    # Step 1 in Telegram: user clicks /start verify_<session_token>
    with SessionLocal() as db:
        res_start = process_telegram_update(
            {
                "update_id": 1001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555001, "first_name": "Timur", "username": "timur_kz"},
                    "chat": {"id": 555001, "type": "private"},
                    "text": f"/start verify_{session_token}",
                },
            },
            db,
        )
        assert res_start["status"] == "ok"
        assert res_start["action"] == "awaiting_contact_verification"

        token_rec = (
            db.query(AccountVerificationToken)
            .filter(AccountVerificationToken.session_token == session_token)
            .first()
        )
        assert token_rec.telegram_verified is False
        assert token_rec.pending_chat_id == "555001"

    # Attempting to verify registration on the website BEFORE sharing contact must fail with HTTP 400
    premature_verify = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": code},
    )
    assert premature_verify.status_code == 400
    assert "confirm your phone number first" in premature_verify.json()["detail"]

    # Step 2 in Telegram: user shares their own matching contact card
    with SessionLocal() as db:
        res_contact = process_telegram_update(
            {
                "update_id": 1002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555001, "first_name": "Timur", "username": "timur_kz"},
                    "chat": {"id": 555001, "type": "private"},
                    "contact": {
                        "phone_number": "77012345678",
                        "user_id": 555001,
                        "first_name": "Timur",
                    },
                },
            },
            db,
        )
        assert res_contact["status"] == "ok"
        assert res_contact["action"] == "registration_code_delivered"
        assert res_contact["code"] == code

    # Poll verification status after sharing contact
    status_after = client.get("/auth/verification-status", params={"identifier": "+77012345678"})
    assert status_after.status_code == 200
    status_json = status_after.json()
    assert status_json["telegram_verified"] is True
    assert status_json["telegram_username"] == "timur_kz"

    # Complete registration on website with 6-digit code
    verify_resp = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": code},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    vdata = verify_resp.json()
    assert "access_token" in vdata
    assert vdata["user"]["is_verified"] is True
    assert vdata["user"]["phone"] == "+77012345678"
    assert vdata["user"]["telegram_chat_id"] == "555001"
    assert vdata["user"]["profile"]["phone"] == "+77012345678"


def test_reject_forwarded_telegram_contact(monkeypatch):
    """
    Ensure forwarding someone else's Telegram contact (contact.user_id != sender chat_id)
    is rejected and does not verify the token.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    reg_resp = client.post(
        "/auth/register",
        json={
            "full_name": "Forwarded Contact Tester",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    )
    session_token = reg_resp.json()["session_token"]

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 2001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555002, "first_name": "Sender"},
                    "chat": {"id": 555002, "type": "private"},
                    "text": f"/start verify_{session_token}",
                },
            },
            db,
        )

        res_forwarded = process_telegram_update(
            {
                "update_id": 2002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555002, "first_name": "Sender"},
                    "chat": {"id": 555002, "type": "private"},
                    "contact": {
                        "phone_number": "+77012345678",
                        "user_id": 999999,  # Different user_id -> forwarded contact!
                        "first_name": "Victim",
                    },
                },
            },
            db,
        )
        assert res_forwarded["status"] == "error"
        assert res_forwarded["reason"] == "forwarded_contact_rejected"

        token_rec = (
            db.query(AccountVerificationToken)
            .filter(AccountVerificationToken.session_token == session_token)
            .first()
        )
        assert token_rec.telegram_verified is False


def test_reject_mismatched_phone_in_telegram_contact(monkeypatch):
    """
    Ensure sharing a Telegram contact whose phone number does not match the phone
    entered on the website is rejected with reason='phone_mismatch'.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    reg_resp = client.post(
        "/auth/register",
        json={
            "full_name": "Mismatch Phone Tester",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    )
    session_token = reg_resp.json()["session_token"]

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 3001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555003, "first_name": "Tester"},
                    "chat": {"id": 555003, "type": "private"},
                    "text": f"/start verify_{session_token}",
                },
            },
            db,
        )

        # User shares their own contact (user_id=555003), but their Telegram phone is +77029876543
        res_mismatch = process_telegram_update(
            {
                "update_id": 3002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555003, "first_name": "Tester"},
                    "chat": {"id": 555003, "type": "private"},
                    "contact": {
                        "phone_number": "+77029876543",
                        "user_id": 555003,
                        "first_name": "Tester",
                    },
                },
            },
            db,
        )
        assert res_mismatch["status"] == "error"
        assert res_mismatch["reason"] == "phone_mismatch"

        token_rec = (
            db.query(AccountVerificationToken)
            .filter(AccountVerificationToken.session_token == session_token)
            .first()
        )
        assert token_rec.telegram_verified is False


# ==============================================================================
# 4. 1-TO-1 TELEGRAM ACCOUNT UNIQUENESS
# ==============================================================================

def test_one_telegram_account_cannot_register_multiple_users(monkeypatch):
    """
    Verify 1-to-1 binding: once Telegram chat_id=777001 is bound to verified User A,
    it cannot be used to verify a second account User B.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    # 1. Register and verify User A (+77012345678) with chat_id = 777001
    reg_a = client.post(
        "/auth/register",
        json={
            "full_name": "User A",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 4001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 777001, "first_name": "UserA"},
                    "chat": {"id": 777001, "type": "private"},
                    "text": f"/start verify_{reg_a['session_token']}",
                },
            },
            db,
        )
        process_telegram_update(
            {
                "update_id": 4002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 777001, "first_name": "UserA"},
                    "chat": {"id": 777001, "type": "private"},
                    "contact": {
                        "phone_number": "+77012345678",
                        "user_id": 777001,
                        "first_name": "UserA",
                    },
                },
            },
            db,
        )

    verify_a = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg_a["debug_code"]},
    )
    assert verify_a.status_code == 200

    # 2. User B registers with a different phone (+77029876543) but tries to use the SAME Telegram chat_id = 777001
    reg_b = client.post(
        "/auth/register",
        json={
            "full_name": "User B",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77029876543",
        },
    ).json()

    with SessionLocal() as db:
        res_b = process_telegram_update(
            {
                "update_id": 4003,
                "message": {
                    "message_id": 3,
                    "from": {"id": 777001, "first_name": "UserA"},
                    "chat": {"id": 777001, "type": "private"},
                    "text": f"/start verify_{reg_b['session_token']}",
                },
            },
            db,
        )
        assert res_b["status"] == "error"
        assert res_b["reason"] == "telegram_already_bound"


# ==============================================================================
# 5. RESEND VERIFICATION TOKEN ROTATION
# ==============================================================================

def test_resend_verification_rotates_session_token_and_preserves_security():
    """
    Calling POST /auth/resend-verification invalidates the old token, rotates
    session_token, and never exposes the 6-digit code in bot_url.
    """
    reg_resp = client.post(
        "/auth/register",
        json={
            "full_name": "Resend User",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    )
    assert reg_resp.status_code == 200
    first_token = reg_resp.json()["session_token"]

    resend_resp = client.post(
        "/auth/resend-verification",
        json={"identifier": "+77012345678"},
    )
    assert resend_resp.status_code == 200
    resend_data = resend_resp.json()
    second_token = resend_data["session_token"]
    new_code = resend_data["debug_code"]
    bot_url = resend_data["bot_url"]

    assert second_token != first_token
    assert len(second_token) == 32
    assert f"?start=verify_{second_token}" in bot_url
    assert new_code not in bot_url


# ==============================================================================
# 6. PASSWORD RESET BY PHONE & HIJACK PREVENTION
# ==============================================================================

def test_password_reset_by_phone_and_hijack_prevention(monkeypatch):
    """
    Verify:
    - /auth/forgot-password accepts phone number in 87... format for a Telegram-registered user
    - bot_url uses opaque ?start=reset_<session_token>
    - An attacker Telegram account (chat_id=999999) clicking the reset deep link is blocked (telegram_mismatch)
    - The legitimate bound Telegram account (chat_id=888001) receives the code
    - /auth/reset-password succeeds using phone number and new password works at login
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    # 1. Register and verify User A with chat_id = 888001
    reg_a = client.post(
        "/auth/register",
        json={
            "full_name": "Reset Owner",
            "password": "OldPassword123!",
            "confirm_password": "OldPassword123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 5001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 888001, "first_name": "Owner"},
                    "chat": {"id": 888001, "type": "private"},
                    "text": f"/start verify_{reg_a['session_token']}",
                },
            },
            db,
        )
        process_telegram_update(
            {
                "update_id": 5002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 888001, "first_name": "Owner"},
                    "chat": {"id": 888001, "type": "private"},
                    "contact": {
                        "phone_number": "77012345678",
                        "user_id": 888001,
                        "first_name": "Owner",
                    },
                },
            },
            db,
        )

    client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg_a["debug_code"]},
    )

    # 2. Request password reset using 87012345678 format and channel="telegram"
    fp_resp = client.post(
        "/auth/forgot-password",
        json={"email": "87012345678", "channel": "telegram"},
    )
    assert fp_resp.status_code == 200
    fp_data = fp_resp.json()
    reset_session_token = fp_data["session_token"]
    reset_code = fp_data["debug_code"]
    assert f"?start=reset_{reset_session_token}" in fp_data["bot_url"]
    assert reset_code not in fp_data["bot_url"]

    # 3. Attacker (chat_id = 999999) clicks /start reset_<session_token> -> blocked!
    with SessionLocal() as db:
        attacker_res = process_telegram_update(
            {
                "update_id": 5003,
                "message": {
                    "message_id": 3,
                    "from": {"id": 999999, "first_name": "Attacker"},
                    "chat": {"id": 999999, "type": "private"},
                    "text": f"/start reset_{reset_session_token}",
                },
            },
            db,
        )
        assert attacker_res["status"] == "error"
        assert attacker_res["reason"] == "telegram_mismatch"

    # 4. Legitimate owner (chat_id = 888001) clicks /start reset_<session_token> -> succeeds!
    with SessionLocal() as db:
        owner_res = process_telegram_update(
            {
                "update_id": 5004,
                "message": {
                    "message_id": 4,
                    "from": {"id": 888001, "first_name": "Owner"},
                    "chat": {"id": 888001, "type": "private"},
                    "text": f"/start reset_{reset_session_token}",
                },
            },
            db,
        )
        assert owner_res["status"] == "ok"
        assert owner_res["action"] == "reset_code_delivered"
        assert owner_res["code"] == reset_code

    # 5. Complete password reset via phone number
    reset_resp = client.post(
        "/auth/reset-password",
        json={
            "email": "+77012345678",
            "code": reset_code,
            "new_password": "NewSecurePassword789!",
            "confirm_password": "NewSecurePassword789!",
        },
    )
    assert reset_resp.status_code == 200

    # 6. Verify login works with the phone number and new password
    login_resp = client.post(
        "/auth/login",
        json={"email": "87012345678", "password": "NewSecurePassword789!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


# ==============================================================================
# 7. PROFILE PHONE LOCKING & SYNCHRONIZATION
# ==============================================================================

def test_profile_phone_locked_when_bound_to_telegram_and_synced(monkeypatch):
    """
    When a user is registered and verified via phone_telegram, their phone number
    is synced to ApplicantProfile and locked against arbitrary changes to another number,
    while updates with the same phone (e.g. formatted as 87012345678) succeed.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    reg = client.post(
        "/auth/register",
        json={
            "full_name": "Profile Lock User",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 6001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555004, "first_name": "ProfileUser"},
                    "chat": {"id": 555004, "type": "private"},
                    "text": f"/start verify_{reg['session_token']}",
                },
            },
            db,
        )
        process_telegram_update(
            {
                "update_id": 6002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555004, "first_name": "ProfileUser"},
                    "chat": {"id": 555004, "type": "private"},
                    "contact": {
                        "phone_number": "+77012345678",
                        "user_id": 555004,
                        "first_name": "ProfileUser",
                    },
                },
            },
            db,
        )

    verify_resp = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg["debug_code"]},
    )
    assert verify_resp.status_code == 200
    jwt_token = verify_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # 1. Attempt to change phone to a different number -> HTTP 400
    bad_update = client.put(
        "/auth/profile",
        json={"phone": "+77029876543", "unt_score": 120},
        headers=headers,
    )
    assert bad_update.status_code == 400
    assert "bound to your Telegram account" in bad_update.json()["detail"]

    # 2. Updating profile with the same phone in 87... format and new scores -> HTTP 200
    good_update = client.put(
        "/auth/profile",
        json={"phone": "87012345678", "unt_score": 125, "ielts_score": 7.0},
        headers=headers,
    )
    assert good_update.status_code == 200
    prof_data = good_update.json()
    assert prof_data["phone"] == "+77012345678"
    assert prof_data["unt_score"] == 125
    assert prof_data["ielts_score"] == 7.0


# ==============================================================================
# 8. ADDITIONAL EDGE CASES: EXPIRED TOKENS & DUPLICATE PHONE PREVENTION
# ==============================================================================

def test_contact_without_pending_token_returns_no_pending_token_error(monkeypatch):
    """
    If a user sends a contact card to the bot without first initiating /start verify_<token>,
    the bot responds with status='error' and reason='no_pending_token'.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    with SessionLocal() as db:
        res = process_telegram_update(
            {
                "update_id": 7001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555001, "first_name": "RandomUser"},
                    "chat": {"id": 555001, "type": "private"},
                    "contact": {
                        "phone_number": "+77012345678",
                        "user_id": 555001,
                        "first_name": "RandomUser",
                    },
                },
            },
            db,
        )
        assert res["status"] == "error"
        assert res["reason"] == "no_pending_token"


def test_duplicate_verified_phone_registration_blocked(monkeypatch):
    """
    Once a phone number (+77012345678) is registered and verified, attempting to
    register again with 87012345678 or +77012345678 is blocked with HTTP 400.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    reg = client.post(
        "/auth/register",
        json={
            "full_name": "Verified Owner",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 8001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555001, "first_name": "Verified"},
                    "chat": {"id": 555001, "type": "private"},
                    "text": f"/start verify_{reg['session_token']}",
                },
            },
            db,
        )
        process_telegram_update(
            {
                "update_id": 8002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555001, "first_name": "Verified"},
                    "chat": {"id": 555001, "type": "private"},
                    "contact": {
                        "phone_number": "+77012345678",
                        "user_id": 555001,
                        "first_name": "Verified",
                    },
                },
            },
            db,
        )

    v_resp = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg["debug_code"]},
    )
    assert v_resp.status_code == 200

    # Re-registering with the same phone in 87... format must return HTTP 400
    dup_resp = client.post(
        "/auth/register",
        json={
            "full_name": "Duplicate Attempt",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "87012345678",
        },
    )
    assert dup_resp.status_code == 400
    assert "already registered" in dup_resp.json()["detail"]


# ==============================================================================
# 9. TELEGRAM UNLINK & ACCOUNT DELETION FROM BOT & WEB
# ==============================================================================

def test_telegram_unlink_via_bot_command(monkeypatch):
    """
    When a Telegram account is already bound to an old user, the user can unlink
    it via /unlink and /confirm_unlink directly in Telegram.
    The bot then automatically prompts to continue any pending registration.
    """
    monkeypatch.setenv("ENFORCE_TELEGRAM_CONTACT", "1")

    # 1. Old User A (+77012345678) registers and verifies with Telegram chat_id = 777001
    reg_a = client.post(
        "/auth/register",
        json={
            "full_name": "Old User A",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 9001,
                "message": {
                    "message_id": 1,
                    "from": {"id": 777001, "first_name": "OldUserA"},
                    "chat": {"id": 777001, "type": "private"},
                    "text": f"/start verify_{reg_a['session_token']}",
                },
            },
            db,
        )
        process_telegram_update(
            {
                "update_id": 9002,
                "message": {
                    "message_id": 2,
                    "from": {"id": 777001, "first_name": "OldUserA"},
                    "chat": {"id": 777001, "type": "private"},
                    "contact": {
                        "phone_number": "+77012345678",
                        "user_id": 777001,
                        "first_name": "OldUserA",
                    },
                },
            },
            db,
        )

    verify_a = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg_a["debug_code"]},
    )
    assert verify_a.status_code == 200

    # 2. User B (+77029876543) tries to register with the SAME Telegram account
    reg_b = client.post(
        "/auth/register",
        json={
            "full_name": "New User B",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77029876543",
        },
    ).json()

    with SessionLocal() as db:
        # User B clicks start link -> receives telegram_already_bound with unlink option
        res_b1 = process_telegram_update(
            {
                "update_id": 9003,
                "message": {
                    "message_id": 3,
                    "from": {"id": 777001, "first_name": "SameOwner"},
                    "chat": {"id": 777001, "type": "private"},
                    "text": f"/start verify_{reg_b['session_token']}",
                },
            },
            db,
        )
        assert res_b1["status"] == "error"
        assert res_b1["reason"] == "telegram_already_bound"

        # 3. User sends /unlink to request unlinking
        prompt_res = process_telegram_update(
            {
                "update_id": 9004,
                "message": {
                    "message_id": 4,
                    "from": {"id": 777001, "first_name": "SameOwner"},
                    "chat": {"id": 777001, "type": "private"},
                    "text": "/unlink",
                },
            },
            db,
        )
        assert prompt_res["status"] == "ok"
        assert prompt_res["action"] == "prompt_unlink_confirmation"

        # 4. User confirms via /confirm_unlink -> unlinks Old User A and prompts contact for New User B!
        confirm_res = process_telegram_update(
            {
                "update_id": 9005,
                "message": {
                    "message_id": 5,
                    "from": {"id": 777001, "first_name": "SameOwner"},
                    "chat": {"id": 777001, "type": "private"},
                    "text": "/confirm_unlink",
                },
            },
            db,
        )
        assert confirm_res["status"] == "ok"
        assert confirm_res["action"] == "unlinked_and_prompted_contact"

        # Verify in DB that Old User A is no longer bound to chat_id = 777001
        old_user = db.query(User).filter(User.phone == "+77012345678").first()
        assert old_user.telegram_chat_id is None

        # 5. Now User B shares their contact (+77029876543) -> registration successfully verified!
        res_b_contact = process_telegram_update(
            {
                "update_id": 9006,
                "message": {
                    "message_id": 6,
                    "from": {"id": 777001, "first_name": "SameOwner"},
                    "chat": {"id": 777001, "type": "private"},
                    "contact": {
                        "phone_number": "+77029876543",
                        "user_id": 777001,
                        "first_name": "SameOwner",
                    },
                },
            },
            db,
        )
        assert res_b_contact["status"] == "ok"
        assert res_b_contact["action"] == "registration_code_delivered"

    verify_b = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77029876543", "code": reg_b["debug_code"]},
    )
    assert verify_b.status_code == 200


def test_telegram_delete_account_via_bot():
    """
    A user can completely delete their bound account via /delete_account and /confirm_delete,
    permanently removing the user record and freeing up Telegram.
    """
    reg = client.post(
        "/auth/register",
        json={
            "full_name": "Delete Me",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77058889900",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 9101,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555004, "first_name": "DeleteMe"},
                    "chat": {"id": 555004, "type": "private"},
                    "text": f"/start verify_{reg['session_token']}",
                },
            },
            db,
        )

    verify = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77058889900", "code": reg["debug_code"]},
    )
    assert verify.status_code == 200

    with SessionLocal() as db:
        # Prompt delete
        prompt_res = process_telegram_update(
            {
                "update_id": 9102,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555004, "first_name": "DeleteMe"},
                    "chat": {"id": 555004, "type": "private"},
                    "text": "/delete_account",
                },
            },
            db,
        )
        assert prompt_res["status"] == "ok"
        assert prompt_res["action"] == "prompt_delete_confirmation"

        # Confirm delete via callback query
        confirm_res = process_telegram_update(
            {
                "update_id": 9103,
                "callback_query": {
                    "id": "cb_del_1",
                    "from": {"id": 555004, "first_name": "DeleteMe"},
                    "data": "confirm_delete",
                },
            },
            db,
        )
        assert confirm_res["status"] == "ok"
        assert confirm_res["action"] == "account_deleted"

        # Assert user was deleted from DB
        deleted_user = db.query(User).filter(User.phone == "+77058889900").first()
        assert deleted_user is None


def test_telegram_status_command():
    """Test /status command returns account info when bound and not_bound when free."""
    reg = client.post(
        "/auth/register",
        json={
            "full_name": "Status User",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 9201,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555001, "first_name": "StatusUser"},
                    "chat": {"id": 555001, "type": "private"},
                    "text": f"/start verify_{reg['session_token']}",
                },
            },
            db,
        )

    client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg["debug_code"]},
    )

    with SessionLocal() as db:
        # Bound user calls /status
        st1 = process_telegram_update(
            {
                "update_id": 9202,
                "message": {
                    "message_id": 2,
                    "from": {"id": 555001, "first_name": "StatusUser"},
                    "chat": {"id": 555001, "type": "private"},
                    "text": "/status",
                },
            },
            db,
        )
        assert st1["status"] == "ok"
        assert st1["action"] == "status_displayed"

        # Unbound user calls /status
        st2 = process_telegram_update(
            {
                "update_id": 9203,
                "message": {
                    "message_id": 3,
                    "from": {"id": 999999, "first_name": "Stranger"},
                    "chat": {"id": 999999, "type": "private"},
                    "text": "/status",
                },
            },
            db,
        )
        assert st2["status"] == "ok"
        assert st2["action"] == "status_not_bound"


def test_web_api_unlink_telegram_and_delete_account():
    """Test POST /auth/unlink-telegram and DELETE /auth/me authenticated endpoints."""
    reg = client.post(
        "/auth/register",
        json={
            "full_name": "API User",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "channel": "phone_telegram",
            "phone": "+77012345678",
        },
    ).json()

    with SessionLocal() as db:
        process_telegram_update(
            {
                "update_id": 9301,
                "message": {
                    "message_id": 1,
                    "from": {"id": 555001, "first_name": "APIUser"},
                    "chat": {"id": 555001, "type": "private"},
                    "text": f"/start verify_{reg['session_token']}",
                },
            },
            db,
        )

    v_resp = client.post(
        "/auth/verify-registration",
        json={"identifier": "+77012345678", "code": reg["debug_code"]},
    )
    token = v_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Unlink Telegram via Web API
    unlink_resp = client.post("/auth/unlink-telegram", headers=headers)
    assert unlink_resp.status_code == 200
    assert unlink_resp.json()["status"] == "ok"

    with SessionLocal() as db:
        u = db.query(User).filter(User.phone == "+77012345678").first()
        assert u.telegram_chat_id is None

    # 2. Delete Account via Web API
    del_resp = client.delete("/auth/me", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ok"

    with SessionLocal() as db:
        u = db.query(User).filter(User.phone == "+77012345678").first()
        assert u is None
