from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Program(Base):
    __tablename__ = "programs"

    id = Column(String, primary_key=True, index=True)
    code = Column(String)
    faculty = Column(String)
    name = Column(String)
    degree = Column(String)
    duration_years = Column(Integer)
    approx_cost_per_year_kzt = Column(Integer)
    format = Column(String)
    language = Column(JSON)  # Stores list of strings
    unt_subjects = Column(JSON)  # Stores list of strings
    description = Column(String)
    aliases = Column(JSON)  # US3 requirement program aliases
    codes = Column(JSON)  # US3 requirement program codes

    # Relationships
    requirements = relationship("Requirement", back_populates="program")


class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(String, primary_key=True, index=True)
    question = Column(String)
    answer = Column(String)
    keywords = Column(JSON)  # Stores list of strings


class Requirement(Base):
    """
    Flattened representation of requirements.json for US3.
    """
    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    program_id = Column(String, ForeignKey("programs.id"), index=True)

    # Classification
    category = Column(String)  # domestic / international
    level = Column(String)  # undergraduate / graduate
    topic = Column(String)  # exams / prerequisites / language

    # Metadata
    status = Column(String)
    source = Column(String)
    checked_on = Column(String)
    verified_on = Column(String)
    review_due = Column(String)
    admission_period = Column(String)
    valid_until = Column(String)
    verification_note = Column(String)

    # Localized texts
    text_en = Column(String)
    text_ru = Column(String)
    text_kk = Column(String)

    # Relationships
    program = relationship("Program", back_populates="requirements")


# ==========================================
# AUTH & USER ACCOUNTS MODELS (RBAC)
# ==========================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="applicant")  # applicant | manager | admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("ApplicantProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    saved_programs = relationship("SavedProgram", back_populates="user", cascade="all, delete-orphan")


class ApplicantProfile(Base):
    __tablename__ = "applicant_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    citizenship = Column(String, default="domestic")  # domestic | international
    target_degree = Column(String, default="undergraduate")  # undergraduate | graduate
    unt_score = Column(Integer, nullable=True)
    ielts_score = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="profile")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String, default="Admissions Inquiry")
    status = Column(String, default="active")  # active | closed | escalated
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), index=True, nullable=False)
    sender = Column(String, nullable=False)  # user | bot | operator
    message = Column(String, nullable=False)
    source = Column(String, nullable=True)  # requirements | program | faq | ai | greeting
    context_state = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")


class SavedProgram(Base):
    __tablename__ = "saved_programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    program_id = Column(String, ForeignKey("programs.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="saved_programs")
    program = relationship("Program")
