"""Admissions and Calculators Router for Sprint 3.

Provides RESTful endpoints for:
- US7: Step-by-Step Admission Guide
- US9: Official Verified Links
- US18: UNT Eligibility Matcher
- US19: Tuition & Grant Calculator
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import (
    AdmissionGuideResponse,
    OfficialLinksResponse,
    UNTMatcherRequest,
    UNTMatcherResponse,
    TuitionCalculatorRequest,
    TuitionCalculatorResponse,
)
from app import database
from app.services.admission_guide import get_admission_guide, GuideUnavailable
from app.services.official_links import get_official_links
from app.services.unt_calculator import match_unt_eligibility
from app.services.tuition_calculator import calculate_tuition_and_grant

router = APIRouter(prefix="/admissions", tags=["Admissions & Calculators"])

CANONICAL_UNT_SUBJECTS = [
    {"value": "Mathematics", "label": "Mathematics (Математика)"},
    {"value": "Computer Science", "label": "Computer Science (Информатика)"},
    {"value": "Physics", "label": "Physics (Физика)"},
    {"value": "Geography", "label": "Geography (География)"},
    {"value": "World History", "label": "World History (Всемирная история)"},
    {"value": "Fundamentals of Law", "label": "Fundamentals of Law (Основы права)"},
    {"value": "Foreign Language", "label": "Foreign Language (Иностранный язык)"},
    {"value": "Creative Exams", "label": "Creative Exams (Творческие экзамены)"},
    {"value": "Biology", "label": "Biology (Биология)"},
    {"value": "Chemistry", "label": "Chemistry (Химия)"},
]


@router.get("/metadata")
def admissions_metadata_endpoint():
    """Return dynamic catalog of academic programs and UNT subjects from the database for UI dropdowns."""
    programs = database.load_programs()
    bachelor_programs = [
        {
            "id": p["id"],
            "code": p.get("code"),
            "name": p["name"],
            "faculty": p.get("faculty"),
            "degree": p.get("degree"),
            "approx_cost_per_year_kzt": p.get("approx_cost_per_year_kzt", 0),
            "unt_subjects": p.get("unt_subjects", []),
        }
        for p in programs
    ]
    return {
        "programs": bachelor_programs,
        "unt_subjects": CANONICAL_UNT_SUBJECTS,
    }


@router.get("/guide", response_model=AdmissionGuideResponse)
def admission_guide_endpoint(
    category: Optional[str] = Query(default="domestic", description="Applicant category: 'domestic' or 'international'"),
    level: Optional[str] = Query(default="undergraduate", description="Degree level: 'undergraduate' or 'graduate'"),
    lang: str = Query(default="ru", description="Response language: 'ru', 'kk', or 'en'"),
    program_id: Optional[str] = Query(default=None, min_length=1, max_length=100),
):
    """US7: Retrieve ordered step-by-step admission procedure guide with localized instructions."""
    try:
        return get_admission_guide(category=category, level=level, lang=lang, program_id=program_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GuideUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/links", response_model=OfficialLinksResponse)
def official_links_endpoint():
    """US9: Retrieve directory of official, verified SDU University links, portals, and contact channels."""
    return get_official_links()


@router.post("/unt-matcher", response_model=UNTMatcherResponse)
def unt_matcher_endpoint(payload: UNTMatcherRequest):
    """US18: Match two UNT profile subjects and total score against SDU bachelor programs."""
    try:
        return match_unt_eligibility(
            subject_1=payload.subject_1,
            subject_2=payload.subject_2,
            score=payload.score
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/tuition-calculator", response_model=TuitionCalculatorResponse)
def tuition_calculator_endpoint(payload: TuitionCalculatorRequest):
    """US19: Calculate tuition costs, eligible scholarship discounts, semester schedule, and state grant probability."""
    try:
        return calculate_tuition_and_grant(
            program_id=payload.program_id,
            unt_score=payload.unt_score,
            discounts=payload.discounts
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
