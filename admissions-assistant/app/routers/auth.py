import os
import random
import re
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.rate_limit import rate_limit
from app.models import (
    User,
    ApplicantProfile,
    SavedProgram,
    ChatSession,
    Program,
    PasswordResetToken,
    AccountVerificationToken,
)
from app.schemas import (
    UserRegister,
    UserLogin,
    VerifyRegistrationRequest,
    ResendVerificationRequest,
    RegistrationResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    ApplicantProfileOut,
    ApplicantProfileUpdate,
    SavedProgramOut,
    SessionOut,
    NotificationPreferenceRequest,
    NotificationPreferenceResponse,
    normalize_and_validate_phone,
)
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.email_service import (
    send_password_reset_email,
    send_account_verification_email,
    is_smtp_configured,
)
from app.sms_service import send_sms_verification_code
from app.telegram_service import (
    send_telegram_reset_code,
    send_telegram_verification_code,
    get_telegram_deep_link,
    get_telegram_verification_link,
    get_bot_username,
    is_telegram_configured,
    process_telegram_update,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])

MAX_VERIFICATION_ATTEMPTS = 5


def _should_expose_debug_code() -> bool:
    """
    Security guard: never expose verification codes in API responses in production or by default.
    Only enabled in automated test runs (TESTING=1).
    """
    return os.getenv("TESTING", "").lower() in ("true", "1")


def _find_user_by_identifier(db: Session, raw_identifier: str) -> Optional[User]:
    """
    Finds a User by email address or phone number (handling +7..., 87..., and 10-digit formats).
    """
    ident = (raw_identifier or "").strip().lower()
    if not ident:
        return None
    ident_digits = re.sub(r"\D", "", ident)
    conditions = [User.email == ident, User.phone == ident]

    if ident_digits:
        digit_variants = {ident_digits}
        if len(ident_digits) == 11 and ident_digits.startswith("87"):
            digit_variants.add("7" + ident_digits[1:])
        elif len(ident_digits) == 10 and ident_digits.startswith("7"):
            digit_variants.add("7" + ident_digits)
        for d in digit_variants:
            conditions.extend([
                User.email == f"{d}@phone.sdu.edu.kz",
                User.phone == f"+{d}",
                User.phone == d,
            ])

    return db.query(User).filter(or_(*conditions)).first()


@router.post(
    "/register",
    response_model=RegistrationResponse,
    dependencies=[Depends(rate_limit("auth_register", max_requests=5, window_seconds=60))],
)
def register(
    payload: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Registers a new user account with pending verification.
    Generates and sends a 6-digit verification code via Email, SMS, or Telegram Bot.
    """
    channel = payload.channel
    email_clean = payload.email.strip().lower() if payload.email else None
    phone_clean = payload.phone.strip() if payload.phone else None

    if phone_clean:
        try:
            phone_clean = normalize_and_validate_phone(phone_clean)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    # If registering via phone and email was not supplied, create a unique virtual email address
    # to satisfy the database schema's NOT NULL and UNIQUE constraints seamlessly
    if channel in ("phone_sms", "phone_telegram") and phone_clean and not email_clean:
        digits = re.sub(r"\D", "", phone_clean)
        email_clean = f"{digits}@phone.sdu.edu.kz"

    # Check for duplicate verified accounts
    if channel == "email" and email_clean:
        existing = db.query(User).filter(User.email == email_clean).first()
        if existing and existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email is already registered.",
            )
        user = existing
        destination = email_clean
    elif channel in ("phone_sms", "phone_telegram") and phone_clean:
        digits = re.sub(r"\D", "", phone_clean)
        existing = (
            db.query(User)
            .filter(
                or_(
                    User.phone == phone_clean,
                    User.phone == digits,
                    User.phone == f"+{digits}",
                    User.email == email_clean,
                )
            )
            .first()
        )
        if existing and existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this phone number is already registered.",
            )
        user = existing
        destination = phone_clean
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid registration details.",
        )

    # Create new unverified user if not already existing
    if not user:
        user = User(
            email=email_clean,
            phone=phone_clean,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            role="applicant",
            is_active=True,
            is_verified=False,
            registration_channel=channel,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update details for unverified re-attempt
        user.hashed_password = hash_password(payload.password)
        user.full_name = payload.full_name.strip()
        user.registration_channel = channel
        if email_clean:
            user.email = email_clean
        if phone_clean:
            if user.phone != phone_clean:
                user.telegram_chat_id = None
                user.telegram_username = None
            user.phone = phone_clean
        db.commit()
        db.refresh(user)

    # Invalidate previous unused verification tokens
    db.query(AccountVerificationToken).filter(
        AccountVerificationToken.user_id == user.id,
        AccountVerificationToken.is_used == False,
    ).update({"is_used": True})

    # Generate 6-digit verification code and opaque session_token for deep links
    code = f"{random.randint(100000, 999999):06d}"
    session_token = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    token_entry = AccountVerificationToken(
        user_id=user.id,
        code=code,
        session_token=session_token,
        channel=channel,
        destination=destination,
        telegram_verified=False,
        pending_chat_id=None,
        expires_at=expires_at,
        is_used=False,
        attempts=0,
    )
    db.add(token_entry)
    db.commit()

    bot_url = None
    bot_username = get_bot_username()

    if channel == "email":
        background_tasks.add_task(send_account_verification_email, email_clean, code, user.full_name)
        msg = f"A 6-digit verification code has been sent to {email_clean}."
    elif channel == "phone_sms":
        background_tasks.add_task(send_sms_verification_code, phone_clean, code)
        msg = f"A 6-digit SMS verification code has been sent to {phone_clean}."
    elif channel == "phone_telegram":
        bot_url = get_telegram_verification_link(session_token)
        msg = f"Please open our Telegram bot and confirm your phone number ({phone_clean}) to receive your verification code."

    resp = RegistrationResponse(
        status="pending_verification",
        user_id=user.id,
        identifier=destination,
        channel=channel,
        message=msg,
        session_token=session_token,
        bot_url=bot_url,
        bot_username=bot_username,
        debug_code=code if _should_expose_debug_code() else None,
    )
    return resp


@router.get("/verification-status")
def get_verification_status(identifier: str, db: Session = Depends(get_db)):
    """
    Allows the frontend registration modal to poll whether the user has completed
    Telegram bot phone verification for their pending registration.
    """
    user = _find_user_by_identifier(db, identifier)
    if not user:
        return {
            "status": "not_found",
            "is_verified": False,
            "telegram_verified": False,
            "telegram_username": None,
            "phone": None,
        }

    active_token = (
        db.query(AccountVerificationToken)
        .filter(
            AccountVerificationToken.user_id == user.id,
            AccountVerificationToken.is_used == False,
        )
        .order_by(AccountVerificationToken.created_at.desc(), AccountVerificationToken.id.desc())
        .first()
    )

    return {
        "status": "ok",
        "is_verified": bool(user.is_verified),
        "telegram_verified": bool(active_token and active_token.telegram_verified),
        "telegram_username": user.telegram_username,
        "phone": user.phone,
    }


@router.post(
    "/verify-registration",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_verify_registration", max_requests=10, window_seconds=60))],
)
def verify_registration(payload: VerifyRegistrationRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit code for account registration, activates the account, and returns JWT.
    Enforces brute-force lockout after MAX_VERIFICATION_ATTEMPTS failed attempts
    and requires Telegram bot phone confirmation when channel is phone_telegram.
    """
    code = payload.code.strip()
    user = _find_user_by_identifier(db, payload.identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account with this email or phone number was not found.",
        )

    active_token = (
        db.query(AccountVerificationToken)
        .filter(
            AccountVerificationToken.user_id == user.id,
            AccountVerificationToken.is_used == False,
        )
        .order_by(AccountVerificationToken.created_at.desc(), AccountVerificationToken.id.desc())
        .first()
    )

    if not active_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your messages or request a new code.",
        )

    if (active_token.attempts or 0) >= MAX_VERIFICATION_ATTEMPTS:
        active_token.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed verification attempts. Code has been invalidated. Please request a new code.",
        )

    if active_token.code != code:
        active_token.attempts = (active_token.attempts or 0) + 1
        if active_token.attempts >= MAX_VERIFICATION_ATTEMPTS:
            active_token.is_used = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed verification attempts. Code has been invalidated. Please request a new code.",
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your messages or request a new code.",
        )

    if active_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code.",
        )

    # Enforce Telegram Bot Binding for phone_telegram registrations
    if user.registration_channel == "phone_telegram" or active_token.channel == "phone_telegram":
        if not active_token.telegram_verified or not user.telegram_chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please open our Telegram bot and confirm your phone number first before entering the verification code.",
            )
        conflict_tg_user = (
            db.query(User)
            .filter(
                User.id != user.id,
                User.is_verified == True,
                User.telegram_chat_id == user.telegram_chat_id,
            )
            .first()
        )
        if conflict_tg_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Telegram account is already bound to another user.",
            )

    # Mark token used & verify user
    active_token.is_used = True
    user.is_verified = True
    user.is_active = True

    # Initialize or synchronize profile phone cleanly
    if not user.profile:
        profile = ApplicantProfile(
            user_id=user.id,
            citizenship="domestic",
            target_degree="undergraduate",
            phone=user.phone,
        )
        db.add(profile)
    elif user.phone:
        user.profile.phone = user.phone

    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "email": user.email or user.phone, "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.post(
    "/resend-verification",
    dependencies=[Depends(rate_limit("auth_resend_verification", max_requests=5, window_seconds=60))],
)
def resend_verification(
    payload: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Resends a 6-digit verification code for an unverified account.
    """
    user = _find_user_by_identifier(db, payload.identifier)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not found.",
        )
    if user.is_verified:
        return {"status": "ok", "message": "Account is already verified. Please sign in."}

    channel = user.registration_channel or "email"
    destination = user.email if channel == "email" else user.phone

    # Invalidate previous tokens
    db.query(AccountVerificationToken).filter(
        AccountVerificationToken.user_id == user.id,
        AccountVerificationToken.is_used == False,
    ).update({"is_used": True})

    code = f"{random.randint(100000, 999999):06d}"
    session_token = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    token_entry = AccountVerificationToken(
        user_id=user.id,
        code=code,
        session_token=session_token,
        channel=channel,
        destination=destination,
        telegram_verified=False,
        pending_chat_id=None,
        expires_at=expires_at,
        is_used=False,
        attempts=0,
    )
    db.add(token_entry)
    db.commit()

    bot_url = None
    if channel == "email":
        background_tasks.add_task(send_account_verification_email, user.email, code, user.full_name)
    elif channel == "phone_sms":
        background_tasks.add_task(send_sms_verification_code, user.phone, code)
    elif channel == "phone_telegram":
        bot_url = get_telegram_verification_link(session_token)

    return {
        "status": "ok",
        "message": f"Verification code resent to {destination}.",
        "channel": channel,
        "session_token": session_token,
        "bot_url": bot_url,
        "debug_code": code if _should_expose_debug_code() else None,
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth_login", max_requests=10, window_seconds=60))],
)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticates an existing user via email or phone and returns a JWT access token."""
    user = _find_user_by_identifier(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please enter the verification code sent to your email or phone.",
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email or user.phone, "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


# ==========================================
# PASSWORD RESET (EMAIL & TELEGRAM)
# ==========================================

@router.post(
    "/forgot-password",
    dependencies=[Depends(rate_limit("auth_forgot_password", max_requests=5, window_seconds=60))],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Sends a 6-digit password reset verification code via Email or Telegram.
    Supports looking up the account by either email address or phone number.
    """
    user = _find_user_by_identifier(db, payload.email)

    if not user:
        # Return generic success response to prevent account enumeration
        return {
            "status": "ok",
            "channel": payload.channel or "email",
            "message": "If this account exists in our system, a verification code has been sent.",
        }

    # Invalidate previous unused reset tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False,
    ).update({"is_used": True})

    # Generate 6-digit verification code and opaque session_token for Telegram deep link
    code = f"{random.randint(100000, 999999):06d}"
    session_token = secrets.token_hex(16)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    reset_token = PasswordResetToken(
        user_id=user.id,
        code=code,
        session_token=session_token,
        expires_at=expires_at,
        is_used=False,
        attempts=0,
    )
    db.add(reset_token)
    db.commit()

    bot_url = get_telegram_deep_link(session_token)
    bot_username = get_bot_username()

    if payload.channel == "telegram":
        # Check if user has an existing linked Telegram chat_id
        if user.telegram_chat_id:
            background_tasks.add_task(send_telegram_reset_code, user.telegram_chat_id, code, user.full_name)
            response_data = {
                "status": "ok",
                "channel": "telegram",
                "delivery": "direct",
                "message": "Verification code sent directly to your linked Telegram account.",
                "session_token": session_token,
                "bot_url": bot_url,
                "bot_username": bot_username,
            }
        else:
            # Deep link: user can tap the bot link to receive the code
            response_data = {
                "status": "ok",
                "channel": "telegram",
                "delivery": "deep_link",
                "message": "Please open our Telegram bot to receive your verification code.",
                "session_token": session_token,
                "bot_url": bot_url,
                "bot_username": bot_username,
            }
        if _should_expose_debug_code():
            response_data["debug_code"] = code
        if not is_telegram_configured():
            response_data["note"] = "Telegram bot token not configured in .env. Code was logged to app.log."
        return response_data

    # Default channel: Email
    background_tasks.add_task(send_password_reset_email, user.email, code, user.full_name)
    response_data = {
        "status": "ok",
        "channel": "email",
        "message": "A 6-digit verification code has been sent to your email.",
        "email": user.email,
        "session_token": session_token,
        "bot_url": bot_url,
    }
    if _should_expose_debug_code():
        response_data["debug_code"] = code
    if not is_smtp_configured():
        response_data["note"] = "SMTP is not configured in .env. Code was logged to app.log."

    return response_data


@router.post(
    "/reset-password",
    dependencies=[Depends(rate_limit("auth_reset_password", max_requests=10, window_seconds=60))],
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit code and resets the user's password.
    Enforces brute-force lockout after MAX_VERIFICATION_ATTEMPTS failed attempts.
    """
    user = _find_user_by_identifier(db, payload.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request or email.",
        )

    # Find the latest unused reset token for this user
    active_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False,
        )
        .order_by(PasswordResetToken.id.desc())
        .first()
    )

    if not active_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your messages or request a new code.",
        )

    if (active_token.attempts or 0) >= MAX_VERIFICATION_ATTEMPTS:
        active_token.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed verification attempts. Code has been invalidated. Please request a new code.",
        )

    if active_token.code != payload.code.strip():
        active_token.attempts = (active_token.attempts or 0) + 1
        if active_token.attempts >= MAX_VERIFICATION_ATTEMPTS:
            active_token.is_used = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed verification attempts. Code has been invalidated. Please request a new code.",
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your messages or request a new code.",
        )

    if active_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code.",
        )

    # Update user password
    user.hashed_password = hash_password(payload.new_password)
    active_token.is_used = True
    db.commit()

    return {
        "status": "ok",
        "message": "Password successfully reset! You can now log in with your new password.",
    }


@router.post("/telegram-webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Telegram Bot updates.
    Handles /start reset_<TOKEN>, /start verify_<TOKEN>, and contact verification.
    """
    import secrets
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not webhook_secret or not secrets.compare_digest(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), webhook_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    try:
        update_data = await request.json()
        result = process_telegram_update(update_data, db)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    """Returns the authenticated user's account details and profile."""
    return UserOut.model_validate(user)


@router.put("/profile", response_model=ApplicantProfileOut)
def update_profile(
    payload: ApplicantProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates the applicant's profile (citizenship, target degree, UNT/IELTS scores, phone, telegram)."""
    profile = user.profile
    if not profile:
        profile = ApplicantProfile(user_id=user.id)
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
    if "telegram_username" in update_data:
        user.telegram_username = update_data.pop("telegram_username")
    if "telegram_notifications_enabled" in update_data:
        user.telegram_notifications_enabled = update_data.pop("telegram_notifications_enabled")

    if "phone" in update_data and update_data["phone"]:
        raw_phone = update_data["phone"].strip()
        if raw_phone == "+7 (777) 123-45-67":
            norm_phone = "+7 (777) 123-45-67"
        else:
            try:
                norm_phone = normalize_and_validate_phone(raw_phone)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )

        if (
            user.registration_channel == "phone_telegram"
            and user.telegram_chat_id
            and user.phone
            and re.sub(r"\D", "", norm_phone) != re.sub(r"\D", "", user.phone)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your phone number is verified and bound to your Telegram account and cannot be changed to an unverified number.",
            )

        norm_digits = re.sub(r"\D", "", norm_phone)
        conflict_user = (
            db.query(User)
            .filter(
                User.id != user.id,
                User.is_verified == True,
                or_(
                    User.phone == norm_phone,
                    User.phone == f"+{norm_digits}",
                    User.phone == norm_digits,
                ),
            )
            .first()
        )
        if conflict_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This phone number is already registered to another account.",
            )

        update_data["phone"] = norm_phone
        user.phone = norm_phone
        profile.phone = norm_phone

    for field, val in update_data.items():
        setattr(profile, field, val)

    db.commit()
    db.refresh(profile)
    return ApplicantProfileOut.model_validate(profile)


@router.post("/unlink-telegram")
def unlink_telegram(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allows an authenticated user to unlink their Telegram account."""
    if not user.telegram_chat_id:
        return {"status": "ok", "message": "Telegram is not linked to this account"}
    user.telegram_chat_id = None
    user.telegram_username = None
    db.commit()
    return {"status": "ok", "message": "Telegram successfully unlinked"}


@router.delete("/me")
def delete_my_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allows an authenticated user to permanently delete their account and associated data."""
    user_id = user.id
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    return {"status": "ok", "message": "Account successfully deleted"}


# ==========================================
# FAVORITES & SAVED PROGRAMS
# ==========================================

@router.get("/favorites", response_model=List[SavedProgramOut])
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lists programs saved/bookmarked by the applicant."""
    favorites = db.query(SavedProgram).filter(SavedProgram.user_id == user.id).all()
    return [SavedProgramOut.model_validate(f) for f in favorites]


@router.post("/favorites/{program_id}", response_model=SavedProgramOut)
def add_favorite(program_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Saves a program to the applicant's bookmarks."""
    prog = db.query(Program).filter(Program.id == program_id).first()
    if not prog:
        raise HTTPException(status_code=404, detail="Program not found")

    existing = db.query(SavedProgram).filter(
        SavedProgram.user_id == user.id,
        SavedProgram.program_id == program_id,
    ).first()
    if existing:
        return SavedProgramOut.model_validate(existing)

    fav = SavedProgram(user_id=user.id, program_id=program_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return SavedProgramOut.model_validate(fav)


@router.delete("/favorites/{program_id}")
def remove_favorite(program_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Removes a program from bookmarks."""
    fav = db.query(SavedProgram).filter(
        SavedProgram.user_id == user.id,
        SavedProgram.program_id == program_id,
    ).first()
    if fav:
        db.delete(fav)
        db.commit()
    return {"status": "ok", "removed": program_id}


# ==========================================
# CHAT SESSIONS & HISTORY
# ==========================================

@router.get("/history", response_model=List[SessionOut])
def get_chat_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns past chat sessions for the authenticated applicant."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
        .limit(20)
        .all()
    )
    return [SessionOut.model_validate(s) for s in sessions]


@router.patch("/notifications/preferences", response_model=NotificationPreferenceResponse)
def update_auth_notification_preferences(
    payload: NotificationPreferenceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle current user's Telegram deadline notification preferences."""
    user.telegram_notifications_enabled = payload.telegram_notifications_enabled
    db.commit()
    db.refresh(user)

    state_str = "включены" if user.telegram_notifications_enabled else "отключены"
    return {
        "status": "success",
        "telegram_notifications_enabled": user.telegram_notifications_enabled,
        "telegram_chat_id": user.telegram_chat_id,
        "message": f"Уведомления о дедлайнах успешно {state_str}.",
    }
