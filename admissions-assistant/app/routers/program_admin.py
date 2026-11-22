"""US10: Staff Program Catalog Manager Router (/admin/programs).

Provides authorized staff (admin, manager) CRUD endpoints for managing
educational program cards (tuition fees, UNT subject pairs, passing scores,
and descriptions) with immediate propagation to catalog, chatbot, and calculators.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import User
from app.schemas import ProgramCreateRequest, ProgramUpdateRequest, ProgramItemOut
from app.security import require_role
from app.services import program_manager

router = APIRouter(
    prefix="/admin/programs",
    tags=["Program Catalog Management"],
    dependencies=[Depends(require_role(["admin", "manager"]))],
)


@router.get("", response_model=List[ProgramItemOut])
def list_admin_programs(
    search: Optional[str] = Query(None, description="Search by code, name, faculty, or description"),
    faculty: Optional[str] = Query(None, description="Filter by faculty name"),
    degree: Optional[str] = Query(None, description="Filter by degree level (Bachelor, Master, PhD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """List all educational program cards for staff management."""
    return program_manager.list_programs(db, search=search, faculty=faculty, degree=degree)


@router.get("/{program_id}", response_model=ProgramItemOut)
def get_admin_program(
    program_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Retrieve a single educational program card by ID."""
    program = program_manager.get_program_by_id(db, program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program with ID '{program_id}' not found.",
        )
    return program_manager.serialize_program(program)


@router.post("", response_model=ProgramItemOut, status_code=status.HTTP_201_CREATED)
def create_admin_program(
    payload: ProgramCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Create a new educational program card in the catalog."""
    actor = current_user.email or current_user.phone or f"user:{current_user.id}"
    try:
        return program_manager.create_program(db=db, payload=payload, actor=actor)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.put("/{program_id}", response_model=ProgramItemOut)
def update_admin_program(
    program_id: str,
    payload: ProgramUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Update an existing educational program card and sync with catalog/calculators."""
    actor = current_user.email or current_user.phone or f"user:{current_user.id}"
    try:
        updated = program_manager.update_program(
            db=db,
            program_id=program_id,
            payload=payload,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program with ID '{program_id}' not found.",
        )
    return updated


@router.delete("/{program_id}")
def delete_admin_program(
    program_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"])),
):
    """Delete an educational program card from the catalog."""
    actor = current_user.email or current_user.phone or f"user:{current_user.id}"
    deleted = program_manager.delete_program(db=db, program_id=program_id, actor=actor)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program with ID '{program_id}' not found.",
        )
    return {
        "status": "deleted",
        "id": program_id,
        "message": "Program deleted successfully",
    }
