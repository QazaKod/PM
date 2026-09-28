from pydantic import BaseModel, Field
from typing import Literal, Optional


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


class ChatResponse(BaseModel):
    answer: str
    confident: bool
    source: Optional[str] = None
    matched_id: Optional[str] = None
    context: Optional[RequirementContext] = None
    requirement_status: Optional[str] = None
    notification_available: bool = False
