from pydantic import BaseModel
from typing import Optional


class ChatQuery(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    confident: bool
    source: Optional[str] = None  # "program" | "faq" | None
    matched_id: Optional[str] = None
