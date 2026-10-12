import os
import random
import re
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_session import get_db
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


@router.post("/register", response_model=RegistrationResponse)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new user account with pending verification.
    Generates and sends a 6-digit verification code via Email, SMS, or Telegram Bot.
    """
    channel = payload.channel
    email_clean = payload.email.strip().lower() if payload.email else None
    phone_clean = payload.phone.strip() if payload.phone else None

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
                detail="User with this email is already registered."
            )
        user = existing
        destination = email_clean
    elif channel in ("phone_sms", "phone_telegram") and phone_clean:
        existing = db.query(User).filter(or_(User.phone == phone_clean, User.email == email_clean)).first()
        if existing and existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this phone number is already registered."
            )
        user = existing
        destination = phone_clean
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid registration details."
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
            user.phone = phone_clean
        db.commit()
        db.refresh(user)

    # Invalidate previous unused verification tokens
    db.query(AccountVerificationToken).filter(
        AccountVerificationToken.user_id == user.id,
        AccountVerificationToken.is_used == False
    ).update({"is_used": True})

    # Generate 6-digit verification code
    code = f"{random.randint(100000, 999999):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    token_entry = AccountVerificationToken(
        user_id=user.id,
        code=code,
        channel=channel,
        destination=destination,
        expires_at=expires_at,
        is_used=False
    )
    db.add(token_entry)
    db.commit()

    bot_url = None
    bot_username = get_bot_username()

    if channel == "email":
        send_account_verification_email(email_clean, code, user.full_name)
        msg = f"A 6-digit verification code has been sent to {email_clean}."
    elif channel == "phone_sms":
        send_sms_verification_code(phone_clean, code)
        msg = f"A 6-digit SMS verification code has been sent to {phone_clean}."
    elif channel == "phone_telegram":
        bot_url = get_telegram_verification_link(code)
        if user.telegram_chat_id:
            send_telegram_verification_code(user.telegram_chat_id, code, user.full_name)
            msg = "Verification code sent directly to your linked Telegram account."
        else:
            msg = f"Please open our Telegram bot to receive your verification code for {phone_clean}."

    resp = RegistrationResponse(
        status="pending_verification",
        user_id=user.id,
        identifier=destination,
        channel=channel,
        message=msg,
        bot_url=bot_url,
        bot_username=bot_username,
        debug_code=code if (os.getenv("DEBUG", "true").lower() in ("true", "1") or os.getenv("TESTING", "").lower() in ("true", "1")) else None
    )
    return resp


@router.post("/verify-registration", response_model=TokenResponse)
def verify_registration(payload: VerifyRegistrationRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit code for account registration, activates the account, and returns JWT.
    """
    ident = payload.identifier.strip().lower()
    code = payload.code.strip()
    ident_digits = re.sub(r"\D", "", ident)

    conditions = [User.email == ident, User.phone == ident]
    if ident_digits:
        conditions.extend([
            User.email == f"{ident_digits}@phone.sdu.edu.kz",
            User.phone == f"+{ident_digits}",
            User.phone == ident_digits,
        ])
    user = db.query(User).filter(or_(*conditions)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account with this email or phone number was not found."
        )

    token_entry = (
        db.query(AccountVerificationToken)
        .filter(
            AccountVerificationToken.user_id == user.id,
            AccountVerificationToken.code == code,
            AccountVerificationToken.is_used == False
        )
        .order_by(AccountVerificationToken.created_at.desc())
        .first()
    )

    if not token_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your messages or request a new code."
        )

    if token_entry.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    # Mark token used & verify user
    token_entry.is_used = True
    user.is_verified = True
    user.is_active = True

    # Initialize profile if not already present
    if not user.profile:
        profile = ApplicantProfile(
            user_id=user.id,
            citizenship="domestic",
            target_degree="undergraduate",
            phone=user.phone
        )
        db.add(profile)
    elif user.phone and not user.profile.phone:
        user.profile.phone = user.phone

    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "email": user.email or user.phone, "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.post("/resend-verification")
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    """
    Resends a 6-digit verification code for an unverified account.
    """
    ident = payload.identifier.strip().lower()
    ident_digits = re.sub(r"\D", "", ident)
    conditions = [User.email == ident, User.phone == ident]
    if ident_digits:
        conditions.extend([
            User.email == f"{ident_digits}@phone.sdu.edu.kz",
            User.phone == f"+{ident_digits}",
            User.phone == ident_digits,
        ])
    user = db.query(User).filter(or_(*conditions)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not found."
        )
    if user.is_verified:
        return {"status": "ok", "message": "Account is already verified. Please sign in."}

    channel = user.registration_channel or "email"
    destination = user.email if channel == "email" else user.phone

    # Invalidate previous tokens
    db.query(AccountVerificationToken).filter(
        AccountVerificationToken.user_id == user.id,
        AccountVerificationToken.is_used == False
    ).update({"is_used": True})

    code = f"{random.randint(100000, 999999):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    token_entry = AccountVerificationToken(
        user_id=user.id,
        code=code,
        channel=channel,
        destination=destination,
        expires_at=expires_at,
        is_used=False
    )
    db.add(token_entry)
    db.commit()

    bot_url = None
    if channel == "email":
        send_account_verification_email(user.email, code, user.full_name)
    elif channel == "phone_sms":
        send_sms_verification_code(user.phone, code)
    elif channel == "phone_telegram":
        bot_url = get_telegram_verification_link(code)
        if user.telegram_chat_id:
            send_telegram_verification_code(user.telegram_chat_id, code, user.full_name)

    return {
        "status": "ok",
        "message": f"Verification code resent to {destination}.",
        "channel": channel,
        "bot_url": bot_url,
        "debug_code": code if (os.getenv("DEBUG", "true").lower() in ("true", "1") or os.getenv("TESTING", "").lower() in ("true", "1")) else None
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticates an existing user via email or phone and returns a JWT access token."""
    ident = payload.email.strip().lower()
    ident_digits = re.sub(r"\D", "", ident)
    conditions = [User.email == ident, User.phone == ident]
    if ident_digits:
        conditions.extend([
            User.email == f"{ident_digits}@phone.sdu.edu.kz",
            User.phone == f"+{ident_digits}",
            User.phone == ident_digits,
        ])
    user = db.query(User).filter(or_(*conditions)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated."
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please enter the verification code sent to your email or phone."
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email or user.phone, "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


# ==========================================
# PASSWORD RESET (EMAIL & TELEGRAM)
# ==========================================

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Sends a 6-digit password reset verification code via Email or Telegram.
    """
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user:
        # Return generic success response to prevent email enumeration
        return {
            "status": "ok",
            "channel": payload.channel or "email",
            "message": "If this account exists in our system, a verification code has been sent."
        }

    # Generate 6-digit verification code
    code = f"{random.randint(100000, 999999):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    reset_token = PasswordResetToken(
        user_id=user.id,
        code=code,
        expires_at=expires_at,
        is_used=False
    )
    db.add(reset_token)
    db.commit()

    bot_url = get_telegram_deep_link(code)
    bot_username = get_bot_username()

    if payload.channel == "telegram":
        # Check if user has an existing linked Telegram chat_id
        if user.telegram_chat_id:
            send_telegram_reset_code(user.telegram_chat_id, code, user.full_name)
            response_data = {
                "status": "ok",
                "channel": "telegram",
                "delivery": "direct",
                "message": f"Verification code sent directly to your linked Telegram account.",
                "bot_url": bot_url,
                "bot_username": bot_username,
            }
        else:
            # Deep link: user can tap the bot link to receive the code
            response_data = {
                "status": "ok",
                "channel": "telegram",
                "delivery": "deep_link",
                "message": f"Please open our Telegram bot to receive your verification code.",
                "bot_url": bot_url,
                "bot_username": bot_username,
            }
        if not is_telegram_configured() or os.getenv("DEBUG", "true").lower() in ("true", "1") or os.getenv("TESTING", "").lower() in ("true", "1"):
            response_data["debug_code"] = code
            if not is_telegram_configured():
                response_data["note"] = "Telegram bot token not configured in .env. Code was logged to app.log."
        return response_data

    # Default channel: Email
    send_password_reset_email(to_email=user.email, code=code, user_name=user.full_name)
    response_data = {
        "status": "ok",
        "channel": "email",
        "message": "A 6-digit verification code has been sent to your email.",
        "email": user.email,
        "bot_url": bot_url,
    }
    if not is_smtp_configured():
        response_data["debug_code"] = code
        response_data["note"] = "SMTP is not configured in .env. Code was logged to app.log."

    return response_data


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit code and resets the user's password.
    """
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request or email."
        )

    # Find the latest matching unused reset token
    token_entry = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.code == payload.code.strip(),
            PasswordResetToken.is_used == False
        )
        .order_by(PasswordResetToken.id.desc())
        .first()
    )

    if not token_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check your messages or request a new code."
        )

    if token_entry.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    # Update user password
    user.hashed_password = hash_password(payload.new_password)
    token_entry.is_used = True
    db.commit()

    return {
        "status": "ok",
        "message": "Password successfully reset! You can now log in with your new password."
    }


@router.post("/telegram-webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Telegram Bot updates.
    Handles /start reset_<CODE> and automatic chat_id linking.
    """
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
    db: Session = Depends(get_db)
):
    """Updates the applicant's profile (citizenship, target degree, UNT/IELTS scores, telegram)."""
    profile = user.profile
    if not profile:
        profile = ApplicantProfile(user_id=user.id)
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
    if "telegram_username" in update_data:
        user.telegram_username = update_data.pop("telegram_username")

    for field, val in update_data.items():
        setattr(profile, field, val)

    db.commit()
    db.refresh(profile)
    return ApplicantProfileOut.model_validate(profile)


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
        SavedProgram.program_id == program_id
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
        SavedProgram.program_id == program_id
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
