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
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=100)
    confirm_password: Optional[str] = Field(default=None, max_length=100)
    channel: Literal["email", "phone_sms", "phone_telegram"] = "email"
    email: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address format.")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Phone number must contain between 10 and 15 digits (e.g. +7 777 123 4567).")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return v

    @model_validator(mode="after")
    def validate_registration_payload(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        if self.channel == "email":
            if not self.email:
                raise ValueError("Email address is required for email registration.")
        elif self.channel in ("phone_sms", "phone_telegram"):
            if not self.phone:
                raise ValueError("Phone number is required for phone registration.")
        return self


class VerifyRegistrationRequest(BaseModel):
    identifier: str
    code: str = Field(min_length=4, max_length=10)

    @field_validator("identifier")
    @classmethod
    def clean_identifier(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str) -> str:
        return v.strip()


class ResendVerificationRequest(BaseModel):
    identifier: str

    @field_validator("identifier")
    @classmethod
    def clean_identifier(cls, v: str) -> str:
        return v.strip().lower()


class RegistrationResponse(BaseModel):
    status: str
    user_id: int
    identifier: str
    channel: str
    message: str
    bot_url: Optional[str] = None
    bot_username: Optional[str] = None
    debug_code: Optional[str] = None


class UserLogin(BaseModel):
    email: str  # Can be email or phone number
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: str
    channel: Optional[Literal["email", "telegram"]] = "email"

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
    telegram_username: Optional[str] = None
    telegram_notifications_enabled: bool = True

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Phone number must contain between 10 and 15 digits (e.g. +7 777 123 4567).")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: str
    role: str
    is_active: bool
    is_verified: bool = False
    created_at: Optional[datetime] = None
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    telegram_notifications_enabled: bool = True
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


# ==========================================
# SPRINT 3: ADMISSIONS & CALCULATORS SCHEMAS
# ==========================================

class AdmissionStepOut(BaseModel):
    id: str
    step: int
    title: str
    timeline: Optional[str] = None
    description: str
    tips: Optional[str] = None
    deadline: Optional[str] = None
    deadline_status: Literal['closed', 'upcoming', 'confirm']
    warning: Optional[str] = None
    source_url: str
    source_title: str


class AdmissionGuideResponse(BaseModel):
    program_id: Optional[str] = None
    program_name: Optional[str] = None
    program_note: Optional[str] = None
    program_note_source: Optional[str] = None
    program_note_verified_on: Optional[str] = None
    version: str
    verified_on: str
    review_due: str
    notice: str
    category: str
    level: str
    language: str
    title: str
    total_steps: int
    steps: List[AdmissionStepOut]
    official_admissions_portal: str
    contacts: Optional[dict] = None


class OfficialLinkItem(BaseModel):
    id: str
    title: str
    name_ru: Optional[str] = None
    url: str
    category: str
    description: Optional[str] = None


class OfficialLinksResponse(BaseModel):
    verified: bool
    total: int
    links: List[OfficialLinkItem]
    urls: dict


class UNTMatcherRequest(BaseModel):
    subject_1: str = Field(min_length=1, max_length=100)
    subject_2: str = Field(min_length=1, max_length=100)
    score: int = Field(ge=0, le=140)


class ProgramMatchItem(BaseModel):
    id: str
    code: Optional[str] = None
    name: str
    faculty: Optional[str] = None
    degree: Optional[str] = "Bachelor"
    min_score: int
    user_score: int
    approx_cost_per_year_kzt: Optional[int] = None
    unt_subjects: List[str] = []
    grant_chance: Optional[str] = None
    grant_cutoff: Optional[int] = None
    points_surplus: Optional[int] = None
    points_needed: Optional[int] = None


class UNTMatcherResponse(BaseModel):
    score: int
    subjects_normalized: List[str]
    total_matched: int
    eligible_programs: List[ProgramMatchItem]
    deficit_programs: List[ProgramMatchItem]
    status_message: str


class TuitionCalculatorRequest(BaseModel):
    program_id: str = Field(min_length=1, max_length=100)
    unt_score: Optional[int] = Field(default=None, ge=0, le=140)
    discounts: Optional[List[str]] = Field(default_factory=list)


class DiscountDetail(BaseModel):
    code: str
    title: str
    percentage: int
    description: Optional[str] = None


class PaymentScheduleDetail(BaseModel):
    semester_1: int
    semester_2: int
    registration_fee: int
    first_payment_total: int
    payment_rules: Optional[str] = None


class GrantProbabilityDetail(BaseModel):
    chance: Optional[str] = None
    estimated_cutoff: int
    field_type: str
    score: Optional[int] = None
    description: str


class TuitionCalculatorResponse(BaseModel):
    program_id: str
    program_code: Optional[str] = None
    program_name: str
    faculty: Optional[str] = None
    degree: str
    duration_years: int
    base_annual_fee: int
    base_total_fee: int
    applied_discounts: List[DiscountDetail]
    raw_discount_percent: int
    total_discount_percent: int
    is_discount_capped: bool
    discount_amount_kzt: int
    discounted_annual_fee: int
    discounted_total_fee: int
    total_savings_kzt: int
    registration_fee_kzt: int
    payment_schedule: PaymentScheduleDetail
    grant_probability: GrantProbabilityDetail



# ==========================================
# SPRINT 4: DEADLINES & CALENDAR SCHEMAS (US8)
# ==========================================

class DeadlineItemOut(BaseModel):
    id: str
    title: str
    stage_name: str
    date_start: str
    date_end: str
    category: str
    degree_level: str
    status: str
    days_left: int
    description: str
    action_url: str
    passed_advice: Optional[str] = None


class DeadlinesListResponse(BaseModel):
    total: int
    reference_date: str
    deadlines: List[DeadlineItemOut]


class CalendarEventOut(BaseModel):
    id: str
    title: str
    stage_name: str
    category: str
    color: str
    date_start: str
    date_end: str
    status: str
    action_url: str


class CalendarDayEventOut(BaseModel):
    id: str
    title: str
    category: str
    color: str
    status: str
    action_url: str


class CalendarMonthOut(BaseModel):
    year: int
    month: int
    month_name: str
    events: List[CalendarEventOut]
    days: dict[int, List[CalendarDayEventOut]]


class CalendarResponse(BaseModel):
    year: int
    total_events: int
    months: List[CalendarMonthOut]


# ==========================================
# SPRINT 4: FAQ MANAGEMENT SCHEMAS (US13)
# ==========================================

class FAQCreateRequest(BaseModel):
    id: Optional[str] = None
    question: str = Field(min_length=3, max_length=1000)
    answer: str = Field(min_length=3, max_length=4000)
    category: Optional[str] = "general"
    keywords: List[str] = Field(default_factory=list)

    @field_validator("question", "answer")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty or whitespace only.")
        return v


class FAQUpdateRequest(BaseModel):
    question: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    answer: Optional[str] = Field(default=None, min_length=3, max_length=4000)
    category: Optional[str] = None
    keywords: Optional[List[str]] = None

    @field_validator("question", "answer")
    @classmethod
    def validate_non_empty_if_set(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Field cannot be empty or whitespace only.")
        return v


class FAQItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    answer: str
    category: Optional[str] = "general"
    keywords: List[str] = Field(default_factory=list)


# ==========================================
# SPRINT 4: TELEGRAM NOTIFICATIONS (US20)
# ==========================================

class NotificationPreferenceRequest(BaseModel):
    telegram_notifications_enabled: bool


class NotificationPreferenceResponse(BaseModel):
    status: str
    telegram_notifications_enabled: bool
    telegram_chat_id: Optional[str] = None
    message: str
