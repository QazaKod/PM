"""US23: Public admissions notices and staff management."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import Announcement
from app.schemas import (
    AnnouncementContent,
    AnnouncementCreate,
    AnnouncementStatusUpdate,
    PublicAnnouncementOut,
    StaffAnnouncementOut,
)
from app.security import require_role


router = APIRouter(tags=["Announcements"])
staff_router = APIRouter(
    prefix="/admin/announcements",
    dependencies=[Depends(require_role(["admin", "manager"]))],
)


@router.get("/announcements", response_model=list[PublicAnnouncementOut])
def list_public_announcements(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return db.scalars(
        select(Announcement).where(Announcement.is_active.is_(True)).order_by(Announcement.id.desc())
    ).all()


@staff_router.get("", response_model=list[StaffAnnouncementOut])
def list_staff_announcements(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return db.scalars(select(Announcement).order_by(Announcement.id.desc())).all()


@staff_router.post("", response_model=StaffAnnouncementOut, status_code=status.HTTP_201_CREATED)
def create_announcement(payload: AnnouncementCreate, db: Session = Depends(get_db)):
    announcement = Announcement(**payload.model_dump(mode="json"))
    db.add(announcement)
    db.flush()
    result = StaffAnnouncementOut.model_validate(announcement)
    db.commit()
    return result


def save_announcement(db: Session, announcement_id: int, values: dict) -> StaffAnnouncementOut:
    announcement = db.execute(
        update(Announcement)
        .where(Announcement.id == announcement_id)
        .values(**values)
        .returning(Announcement)
    ).scalar_one_or_none()
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    result = StaffAnnouncementOut.model_validate(announcement)
    db.commit()
    return result


@staff_router.put("/{announcement_id}", response_model=StaffAnnouncementOut)
def edit_announcement(announcement_id: int, payload: AnnouncementContent, db: Session = Depends(get_db)):
    return save_announcement(db, announcement_id, payload.model_dump(mode="json"))


@staff_router.patch("/{announcement_id}/status", response_model=StaffAnnouncementOut)
def set_announcement_status(announcement_id: int, payload: AnnouncementStatusUpdate, db: Session = Depends(get_db)):
    return save_announcement(db, announcement_id, payload.model_dump())


@staff_router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(announcement_id: int, db: Session = Depends(get_db)):
    deleted_id = db.execute(
        delete(Announcement).where(Announcement.id == announcement_id).returning(Announcement.id)
    ).scalar_one_or_none()
    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(staff_router)
