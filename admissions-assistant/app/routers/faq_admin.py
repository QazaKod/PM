"""US13: Manage FAQ Database Router (/admin/faqs).

Provides authorized staff CRUD operations for FAQ management with role-based
access control (RBAC: admin, manager) and instant chatbot hot-reloading.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import User
from app.schemas import FAQCreateRequest, FAQUpdateRequest, FAQItemOut
from app.security import require_role
from app.services import faq_manager

logger = logging.getLogger("admissions_api")

router = APIRouter(
    prefix="/admin/faqs",
    tags=["FAQ Management"],
    dependencies=[Depends(require_role(["admin", "manager"]))],
)


@router.get("", response_model=List[FAQItemOut])
def list_faqs(
    category: Optional[str] = Query(None, description="Filter FAQs by category"),
    search: Optional[str] = Query(None, description="Search question or answer keywords"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Retrieve all FAQ entries with optional category filtering and search."""
    return faq_manager.get_all_faqs(db, category=category, search=search)


@router.post("", response_model=FAQItemOut, status_code=status.HTTP_201_CREATED)
def create_faq_entry(
    payload: FAQCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Create a new FAQ entry (staff only) with real-time chatbot hot-reload."""
    try:
        faq = faq_manager.create_faq(
            db=db,
            question=payload.question,
            answer=payload.answer,
            category=payload.category,
            keywords=payload.keywords,
            faq_id=payload.id,
        )
        return faq
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{faq_id}", response_model=FAQItemOut)
def update_faq_entry(
    faq_id: str,
    payload: FAQUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Update question, answer, category, or keywords of an existing FAQ entry."""
    try:
        updated = faq_manager.update_faq(
            db=db,
            faq_id=faq_id,
            question=payload.question,
            answer=payload.answer,
            category=payload.category,
            keywords=payload.keywords,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FAQ entry with ID '{faq_id}' not found.",
            )
        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{faq_id}")
def delete_faq_entry(
    faq_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Delete an FAQ entry from the database with real-time chatbot hot-reload."""
    deleted = faq_manager.delete_faq(db, faq_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FAQ entry with ID '{faq_id}' not found.",
        )
    return {
        "status": "deleted",
        "id": faq_id,
        "message": "FAQ entry deleted successfully",
    }
