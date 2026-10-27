"""US13: Manage FAQ Database Service (CRUD & Real-Time Hot-Reloading).

Provides authorized staff operations for admissions FAQ management with
immediate synchronization into chatbot in-memory matching engine.
"""

import uuid
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import FAQ

logger = logging.getLogger("admissions_api")


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
