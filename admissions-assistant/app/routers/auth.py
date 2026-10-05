from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import User, ApplicantProfile, SavedProgram, ChatSession, Program
from app.schemas import (
    UserRegister,
    UserLogin,
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

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])


@router.post("/register", response_model=TokenResponse)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Registers a new applicant account and initializes their profile."""
    email_clean = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email is already registered."
        )

    user = User(
        email=email_clean,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="applicant",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize default applicant profile
    profile = ApplicantProfile(
        user_id=user.id,
        citizenship="domestic",
        target_degree="undergraduate"
    )
    db.add(profile)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticates an existing user and returns a JWT access token."""
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
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

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


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
    """Updates the applicant's profile (citizenship, target degree, UNT/IELTS scores)."""
    profile = user.profile
    if not profile:
        profile = ApplicantProfile(user_id=user.id)
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
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
