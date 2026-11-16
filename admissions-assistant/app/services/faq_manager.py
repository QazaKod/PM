"""US13 & US22: Manage FAQ Database & Unanswered Queries Service.

Provides authorized staff operations for admissions FAQ management with
immediate synchronization into chatbot in-memory matching engine, plus
fallback query logging and one-click FAQ conversion.
"""

import re
import uuid
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_

from app.models import FAQ, ChatSession, ChatMessage

logger = logging.getLogger("admissions_api")

_BASIC_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "what", "how", "can", "you",
    "are", "does", "from", "about", "что", "как", "для", "или", "где", "это",
    "мне", "есть", "при", "про", "үшін", "және", "қалай", "қандай",
}


def reload_faq_cache():
    """Hot-reloads FAQ entries into the chatbot engine without server restart."""
    try:
        from app import chatbot
        if hasattr(chatbot, "reload_faqs"):
            reloaded = chatbot.reload_faqs()
            logger.info(f"🔄 FAQ hot-reloaded successfully. Total active entries: {len(reloaded)}")
            return reloaded
    except Exception as e:
        logger.warning(f"⚠️ Failed to hot-reload chatbot FAQs: {e}")
    return None


def get_all_faqs(
    db: Session,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> List[FAQ]:
    """Retrieves all FAQ entries with optional category filtering and search."""
    query = db.query(FAQ)
    if category:
        query = query.filter(FAQ.category == category)
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                FAQ.question.ilike(search_pattern),
                FAQ.answer.ilike(search_pattern),
            )
        )
    return query.order_by(FAQ.id).all()


def get_faq_by_id(db: Session, faq_id: str) -> Optional[FAQ]:
    """Retrieves a single FAQ entry by its unique identifier."""
    return db.query(FAQ).filter(FAQ.id == faq_id).first()


def create_faq(
    db: Session,
    question: str,
    answer: str,
    category: Optional[str] = "general",
    keywords: Optional[List[str]] = None,
    faq_id: Optional[str] = None,
    unanswered_query_id: Optional[int] = None,
) -> FAQ:
    """Creates a new FAQ entry, persists it, and hot-reloads chatbot knowledge base."""
    q_clean = question.strip() if question else ""
    a_clean = answer.strip() if answer else ""
    if not q_clean or not a_clean:
        raise ValueError("FAQ question and answer must be non-empty.")

    entry_id = faq_id.strip() if faq_id and faq_id.strip() else f"faq_{uuid.uuid4().hex[:8]}"

    # Ensure uniqueness of entry_id
    existing = get_faq_by_id(db, entry_id)
    if existing:
        raise ValueError(f"FAQ entry with ID '{entry_id}' already exists.")

    cleaned_keywords = [k.strip() for k in (keywords or []) if k and k.strip()]

    new_faq = FAQ(
        id=entry_id,
        question=q_clean,
        answer=a_clean,
        category=(category or "general").strip(),
        keywords=cleaned_keywords,
    )
    db.add(new_faq)
    db.commit()
    db.refresh(new_faq)

    reload_faq_cache()
    if unanswered_query_id is not None:
        mark_unanswered_query_status(
            db,
            query_id=unanswered_query_id,
            new_status="converted",
            converted_faq_id=new_faq.id,
        )
    logger.info(f"✅ Created FAQ entry '{new_faq.id}' (Category: {new_faq.category})")
    return new_faq


def update_faq(
    db: Session,
    faq_id: str,
    question: Optional[str] = None,
    answer: Optional[str] = None,
    category: Optional[str] = None,
    keywords: Optional[List[str]] = None,
) -> Optional[FAQ]:
    """Updates an existing FAQ entry, persists changes, and hot-reloads chatbot knowledge base."""
    faq = get_faq_by_id(db, faq_id)
    if not faq:
        return None

    if question is not None:
        q_clean = question.strip()
        if not q_clean:
            raise ValueError("FAQ question cannot be empty.")
        faq.question = q_clean

    if answer is not None:
        a_clean = answer.strip()
        if not a_clean:
            raise ValueError("FAQ answer cannot be empty.")
        faq.answer = a_clean

    if category is not None:
        faq.category = category.strip() or "general"

    if keywords is not None:
        faq.keywords = [k.strip() for k in keywords if k and k.strip()]

    db.commit()
    db.refresh(faq)

    reload_faq_cache()
    logger.info(f"✅ Updated FAQ entry '{faq.id}'")
    return faq


def delete_faq(db: Session, faq_id: str) -> bool:
    """Deletes an FAQ entry from the database and hot-reloads chatbot knowledge base."""
    faq = get_faq_by_id(db, faq_id)
    if not faq:
        return False

    db.delete(faq)
    db.commit()

    reload_faq_cache()
    logger.info(f"🗑️ Deleted FAQ entry '{faq_id}'")
    return True


# ==========================================
# US22: UNANSWERED CHATBOT QUERIES LOG
# ==========================================

def _extract_keywords_from_question(question: str, limit: int = 8) -> List[str]:
    tokens = re.findall(r"[a-zA-Zа-яёА-ЯЁәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9]+", (question or "").lower())
    seen = set()
    extracted = []
    for token in tokens:
        if len(token) >= 3 and token not in _BASIC_STOPWORDS and token not in seen:
            seen.add(token)
            extracted.append(token)
            if len(extracted) >= limit:
                break
    return extracted


def _serialize_unanswered_message(msg: ChatMessage, session_user_id: Optional[int] = None) -> dict:
    ctx = msg.context_state if isinstance(msg.context_state, dict) else {}
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "user_id": session_user_id,
        "question": msg.message,
        "bot_response": ctx.get("bot_answer") or "",
        "status": ctx.get("review_status", "pending"),
        "converted_faq_id": ctx.get("converted_faq_id"),
        "timestamp": msg.timestamp,
    }


def record_fallback_query(
    db: Session,
    question: str,
    bot_answer: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    context_state: Optional[dict] = None,
) -> ChatMessage:
    """Persist an unconfident/fallback chat turn so staff can review and convert it to FAQ."""
    session = None
    if session_id:
        query = db.query(ChatSession).filter(ChatSession.id == session_id)
        if user_id is not None:
            query = query.filter(ChatSession.user_id == user_id)
        else:
            query = query.filter(ChatSession.user_id.is_(None))
        session = query.first()

    if not session:
        sid = session_id if (session_id and not db.query(ChatSession).filter(ChatSession.id == session_id).first()) else str(uuid.uuid4())
        session = ChatSession(
            id=sid,
            user_id=user_id,
            title=question[:40] + ("..." if len(question) > 40 else ""),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    user_ctx = dict(context_state) if isinstance(context_state, dict) else {}
    user_ctx["review_status"] = "pending"
    user_ctx["bot_answer"] = bot_answer

    user_msg = ChatMessage(
        session_id=session.id,
        sender="user",
        message=question,
        source="fallback",
        context_state=user_ctx,
    )
    bot_msg = ChatMessage(
        session_id=session.id,
        sender="bot",
        message=bot_answer,
        source="fallback",
        context_state=context_state,
    )
    db.add(user_msg)
    db.add(bot_msg)
    db.commit()
    db.refresh(user_msg)
    return user_msg


def get_unanswered_queries(
    db: Session,
    status_filter: Optional[str] = "pending",
    search: Optional[str] = None,
) -> List[dict]:
    """Return logged fallback chat questions for staff review."""
    query = (
        db.query(ChatMessage, ChatSession.user_id)
        .outerjoin(ChatSession, ChatMessage.session_id == ChatSession.id)
        .filter(ChatMessage.sender == "user", ChatMessage.source == "fallback")
    )
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(ChatMessage.message.ilike(pattern))

    rows = query.order_by(ChatMessage.timestamp.desc(), ChatMessage.id.desc()).all()
    items = [_serialize_unanswered_message(msg, uid) for msg, uid in rows]
    if status_filter and status_filter != "all":
        items = [item for item in items if item["status"] == status_filter]
    return items


def mark_unanswered_query_status(
    db: Session,
    query_id: int,
    new_status: str,
    converted_faq_id: Optional[str] = None,
) -> Optional[dict]:
    """Update review_status on a fallback ChatMessage (pending | converted | dismissed)."""
    msg = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.id == query_id,
            ChatMessage.sender == "user",
            ChatMessage.source == "fallback",
        )
        .first()
    )
    if not msg:
        return None

    ctx = dict(msg.context_state) if isinstance(msg.context_state, dict) else {}
    ctx["review_status"] = new_status
    if converted_faq_id is not None:
        ctx["converted_faq_id"] = converted_faq_id
    msg.context_state = ctx
    flag_modified(msg, "context_state")
    db.commit()
    db.refresh(msg)
    uid = msg.session.user_id if msg.session else None
    return _serialize_unanswered_message(msg, uid)


def convert_unanswered_to_faq(
    db: Session,
    query_id: int,
    answer: str,
    question: Optional[str] = None,
    category: Optional[str] = "general",
    keywords: Optional[List[str]] = None,
) -> dict:
    """Create a new FAQ from an unanswered query, hot-reload chatbot, and mark query converted."""
    msg = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.id == query_id,
            ChatMessage.sender == "user",
            ChatMessage.source == "fallback",
        )
        .first()
    )
    if not msg:
        raise LookupError(f"Unanswered query with ID '{query_id}' not found.")

    final_question = question.strip() if question and question.strip() else msg.message.strip()
    cleaned_keywords = [k.strip() for k in (keywords or []) if k and k.strip()]
    if not cleaned_keywords:
        cleaned_keywords = _extract_keywords_from_question(final_question)

    faq = create_faq(
        db=db,
        question=final_question,
        answer=answer,
        category=category,
        keywords=cleaned_keywords,
    )
    updated_query = mark_unanswered_query_status(
        db=db,
        query_id=query_id,
        new_status="converted",
        converted_faq_id=faq.id,
    )
    return {"faq": faq, "query": updated_query}
