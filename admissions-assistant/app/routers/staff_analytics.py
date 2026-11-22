"""US6: Summary analytics for admissions staff."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import ApplicantProfile, ChatSession, Program, SavedProgram, User
from app.schemas import StaffAnalyticsOut
from app.security import require_role


router = APIRouter(
    prefix="/admin/analytics",
    tags=["Staff Analytics"],
    dependencies=[Depends(require_role(["admin", "manager"]))],
)


@router.get("", response_model=StaffAnalyticsOut)
def get_staff_analytics(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"

    registrations = dict(
        db.execute(
            select(ApplicantProfile.citizenship, func.count(User.id))
            .select_from(User)
            .outerjoin(ApplicantProfile, ApplicantProfile.user_id == User.id)
            .where(User.role == "applicant")
            .group_by(ApplicantProfile.citizenship)
        ).all()
    )
    domestic = registrations.get("domestic", 0)
    international = registrations.get("international", 0)
    total_applicants = sum(registrations.values())

    saved_count = func.count(func.distinct(SavedProgram.user_id)).label("saved_count")
    top_programs = db.execute(
        select(Program.id.label("program_id"), func.coalesce(Program.name, Program.id).label("name"), saved_count)
        .join(SavedProgram, SavedProgram.program_id == Program.id)
        .join(User, User.id == SavedProgram.user_id)
        .where(User.role == "applicant")
        .group_by(Program.id, Program.name)
        .order_by(saved_count.desc(), func.lower(Program.name), Program.id)
        .limit(10)
    ).mappings()

    return {
        "total_applicants": total_applicants,
        "domestic_applicants": domestic,
        "international_applicants": international,
        "unspecified_applicants": total_applicants - domestic - international,
        "total_chat_sessions": db.scalar(select(func.count()).select_from(ChatSession)),
        "top_saved_programs": list(top_programs),
    }
