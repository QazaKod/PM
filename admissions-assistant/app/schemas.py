import re
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal, Optional, List


# ==========================================
# CHATBOT SCHEMAS
# ==========================================

class RequirementContext(BaseModel):
    admission_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    program_id: Optional[str] = Field(default=None, max_length=100)
    category: Optional[Literal['domestic', 'international']] = None
    study_level: Optional[Literal['undergraduate', 'graduate']] = None
    language: Literal['en', 'ru', 'kk'] = 'en'
    topics: list[Literal['exams', 'prerequisites', 'language']] = Field(default_factory=list, max_length=3)
    pending: Optional[Literal['program_id', 'category', 'study_level']] = None


class ChatQuery(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: Optional[RequirementContext] = None
    language: Optional[Literal['en', 'ru', 'kk']] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    confident: bool
    source: Optional[str] = None
    matched_id: Optional[str] = None
    context: Optional[RequirementContext] = None
    requirement_status: Optional[str] = None
    notification_available: bool = False
    session_id: Optional[str] = None


# ==========================================
# AUTH & PROFILE SCHEMAS
# ==========================================

class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=100)
    confirm_password: Optional[str] = Field(default=None, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address format.")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return v

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str = Field(min_length=6, max_length=100)
    confirm_password: str = Field(min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("New passwords do not match.")
        return self



class ApplicantProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    citizenship: Optional[str] = "domestic"
    target_degree: Optional[str] = "undergraduate"
    unt_score: Optional[int] = None
    ielts_score: Optional[float] = None
    phone: Optional[str] = None


class ApplicantProfileUpdate(BaseModel):
    citizenship: Optional[Literal["domestic", "international"]] = None
    target_degree: Optional[Literal["undergraduate", "graduate"]] = None
    unt_score: Optional[int] = Field(default=None, ge=0, le=140)
    ielts_score: Optional[float] = Field(default=None, ge=0.0, le=9.0)
    phone: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        # Count digits only to verify standard phone length
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Phone number must contain between 10 and 15 digits (e.g. +7 777 123 4567).")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    profile: Optional[ApplicantProfileOut] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ==========================================
# CHAT SESSIONS & HISTORY SCHEMAS
# ==========================================

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: str
    message: str
    source: Optional[str] = None
    timestamp: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    created_at: datetime
    messages: List[MessageOut] = []


class SavedProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: str
    created_at: datetime
