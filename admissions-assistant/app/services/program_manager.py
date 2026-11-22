"""US10: Staff Program Catalog Manager Service.

Provides authorized staff CRUD operations for educational program cards
(tuition fee, UNT subject pairs, passing scores, duration, description, etc.)
stored in SQLite so updates immediately propagate to the public catalog,
chatbot, and UNT/tuition calculators without restarting the server.
"""

import logging
import re
import uuid
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Program, Requirement, SavedProgram
from app.schemas import ProgramCreateRequest, ProgramUpdateRequest
from app.services.unt_calculator import get_program_threshold, normalize_subject

logger = logging.getLogger("admissions_api")


def _slugify_program_id(name: str, code: str) -> str:
    """Build a deterministic URL-safe program ID like 'sdu-data-science'."""
    raw = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not raw:
        raw = re.sub(r"[^a-z0-9]+", "-", (code or "").lower()).strip("-")
    if not raw:
        raw = uuid.uuid4().hex[:8]
    base = raw if raw.startswith("sdu-") else f"sdu-{raw}"
    return base[:64].rstrip("-")


def _normalize_unt_subjects(subjects: List[str]) -> List[str]:
    """Normalize known UNT subjects to canonical English names while rejecting duplicates."""
    normalized: List[str] = []
    seen = set()
    for raw in subjects or []:
        cleaned = (raw or "").strip()
        if not cleaned:
            continue
        canon = normalize_subject(cleaned)
        key = canon.lower()
        if key in seen:
            raise ValueError(f"Duplicate UNT profile subject '{canon}' is not allowed.")
        seen.add(key)
        normalized.append(canon)
    return normalized


def serialize_program(program: Program) -> Dict:
    """Serialize a Program ORM object including its effective UNT passing threshold."""
    effective_threshold = get_program_threshold(
        program.id,
        program.faculty or "",
        program.min_unt_score,
    )
    return {
        "id": program.id,
        "code": program.code or "",
        "faculty": program.faculty or "",
        "name": program.name or "",
        "degree": program.degree or "Bachelor",
        "duration_years": int(program.duration_years or 4),
        "approx_cost_per_year_kzt": int(program.approx_cost_per_year_kzt or 0),
        "format": program.format or "Full-time",
        "language": list(program.language or []),
        "unt_subjects": list(program.unt_subjects or []),
        "min_unt_score": program.min_unt_score,
        "effective_min_unt_score": effective_threshold,
        "description": program.description or "",
        "aliases": list(program.aliases or []),
    }


def list_programs(
    db: Session,
    search: Optional[str] = None,
    faculty: Optional[str] = None,
    degree: Optional[str] = None,
) -> List[Dict]:
    """Return educational programs with optional search, faculty, and degree filters."""
    query = db.query(Program)

    if faculty and faculty.strip() and faculty.strip().lower() != "all":
        query = query.filter(Program.faculty == faculty.strip())

    if degree and degree.strip() and degree.strip().lower() != "all":
        query = query.filter(Program.degree.ilike(degree.strip()))

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Program.id.ilike(pattern),
                Program.code.ilike(pattern),
                Program.name.ilike(pattern),
                Program.faculty.ilike(pattern),
                Program.description.ilike(pattern),
            )
        )

    programs = query.order_by(Program.faculty, Program.name).all()
    return [serialize_program(p) for p in programs]


def get_program_by_id(db: Session, program_id: str) -> Optional[Program]:
    """Retrieve a single Program ORM row by ID."""
    return db.query(Program).filter(Program.id == program_id).first()


def create_program(
    db: Session,
    payload: ProgramCreateRequest,
    actor: Optional[str] = None,
) -> Dict:
    """Create a new educational program card after validating uniqueness and domain rules."""
    if payload.id:
        program_id = payload.id
        if get_program_by_id(db, program_id):
            raise ValueError(f"Program with ID '{program_id}' already exists.")
    else:
        base_id = _slugify_program_id(payload.name, payload.code)
        program_id = base_id
        suffix = 2
        while get_program_by_id(db, program_id):
            program_id = f"{base_id}-{suffix}"
            suffix += 1

    unt_subjects = _normalize_unt_subjects(payload.unt_subjects)

    program = Program(
        id=program_id,
        code=payload.code,
        faculty=payload.faculty,
        name=payload.name,
        degree=payload.degree,
        duration_years=payload.duration_years,
        approx_cost_per_year_kzt=payload.approx_cost_per_year_kzt,
        format=payload.format,
        language=payload.language,
        unt_subjects=unt_subjects,
        min_unt_score=payload.min_unt_score,
        description=payload.description,
        aliases=payload.aliases,
        codes={"gop": payload.code},
    )
    db.add(program)
    db.commit()
    db.refresh(program)

    logger.info(
        "US10 Program created: id=%s name=%s cost=%s actor=%s",
        program.id,
        program.name,
        program.approx_cost_per_year_kzt,
        actor or "unknown",
    )
    return serialize_program(program)


def update_program(
    db: Session,
    program_id: str,
    payload: ProgramUpdateRequest,
    actor: Optional[str] = None,
) -> Optional[Dict]:
    """Update an existing educational program card with partial or full fields."""
    program = get_program_by_id(db, program_id)
    if not program:
        return None

    fields_set = payload.model_fields_set

    if "code" in fields_set:
        if payload.code is None:
            raise ValueError("Program code cannot be null.")
        program.code = payload.code
        existing_codes = dict(program.codes or {})
        existing_codes["gop"] = payload.code
        program.codes = existing_codes

    if "faculty" in fields_set:
        if payload.faculty is None:
            raise ValueError("Faculty cannot be null.")
        program.faculty = payload.faculty

    if "name" in fields_set:
        if payload.name is None:
            raise ValueError("Program name cannot be null.")
        program.name = payload.name

    if "degree" in fields_set:
        if payload.degree is None:
            raise ValueError("Degree cannot be null.")
        program.degree = payload.degree

    if "duration_years" in fields_set:
        if payload.duration_years is None or payload.duration_years <= 0:
            raise ValueError("Duration years must be a positive integer.")
        program.duration_years = payload.duration_years

    if "approx_cost_per_year_kzt" in fields_set:
        if payload.approx_cost_per_year_kzt is None or payload.approx_cost_per_year_kzt <= 0:
            raise ValueError("Tuition cost must be a positive number.")
        program.approx_cost_per_year_kzt = payload.approx_cost_per_year_kzt

    if "format" in fields_set:
        if payload.format is None:
            raise ValueError("Study format cannot be null.")
        program.format = payload.format

    if "language" in fields_set:
        if payload.language is None:
            raise ValueError("Language list cannot be null.")
        program.language = payload.language

    if "unt_subjects" in fields_set:
        if payload.unt_subjects is None:
            program.unt_subjects = []
        else:
            program.unt_subjects = _normalize_unt_subjects(payload.unt_subjects)

    if "min_unt_score" in fields_set:
        program.min_unt_score = payload.min_unt_score

    if "description" in fields_set:
        if payload.description is None:
            raise ValueError("Description cannot be null.")
        program.description = payload.description

    if "aliases" in fields_set:
        program.aliases = payload.aliases or []

    db.commit()
    db.refresh(program)

    logger.info(
        "US10 Program updated: id=%s fields=%s actor=%s",
        program.id,
        sorted(fields_set),
        actor or "unknown",
    )
    return serialize_program(program)


def delete_program(
    db: Session,
    program_id: str,
    actor: Optional[str] = None,
) -> bool:
    """Delete an educational program and its dependent bookmarks/requirements safely."""
    program = get_program_by_id(db, program_id)
    if not program:
        return False

    # Clear dependent rows first so PRAGMA foreign_keys=ON never raises IntegrityError
    db.query(SavedProgram).filter(SavedProgram.program_id == program_id).delete(synchronize_session=False)
    db.query(Requirement).filter(Requirement.program_id == program_id).delete(synchronize_session=False)
    db.delete(program)
    db.commit()

    logger.info("US10 Program deleted: id=%s actor=%s", program_id, actor or "unknown")
    return True
