from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import ChatSession, ChatMessage, OfficerPresence, OfficerRequest, SessionRating, ConsultationSetting
from app.security import get_current_user, require_role

router = APIRouter(tags=["Consultations"])
staff = require_role(["manager", "admin"])


class Handoff(BaseModel):
    session_id: str
    callback: str | None = Field(None, max_length=200)


class Rating(BaseModel):
    session_id: str
    score: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=1000)


class Reply(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=4000)


class Threshold(BaseModel):
    value: float = Field(gt=0, le=1)


def owned(db, sid, user):
    session = db.query(ChatSession).filter_by(id=sid, user_id=user.id).first()
    if not session:
        raise HTTPException(404, "Conversation not found.")
    return session


def transcript(db, sid):
    return [{"id": m.id, "sender": m.sender, "message": m.message}
            for m in db.query(ChatMessage).filter_by(session_id=sid).order_by(ChatMessage.id)]


@router.post("/handoff")
def request_officer(data: Handoff, db: Session = Depends(get_db), user=Depends(get_current_user)):
    session = owned(db, data.session_id, user)
    online = db.query(OfficerPresence).filter(OfficerPresence.seen_at >= datetime.utcnow() - timedelta(seconds=45)).first()
    callback = (data.callback or user.email or user.phone or "").strip()
    if not online and not callback:
        raise HTTPException(422, "Provide a callback email or phone.")
    request = db.get(OfficerRequest, session.id)
    if not request:
        session.status = "escalated"
        db.add(OfficerRequest(session_id=session.id, callback=callback))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not db.get(OfficerRequest, session.id):
                raise
    return {"online": bool(online), "session_id": session.id}


@router.get("/handoff/current")
def current_request(db: Session = Depends(get_db), user=Depends(get_current_user)):
    latest = (db.query(ChatSession).join(OfficerRequest)
              .filter(ChatSession.user_id == user.id).order_by(ChatSession.created_at.desc()).first())
    return {"session_id": latest.id if latest else None}


@router.get("/handoff/{sid}")
def applicant_thread(sid: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    owned(db, sid, user)
    if not db.get(OfficerRequest, sid):
        raise HTTPException(410, "The officer has closed this consultation.")
    return transcript(db, sid)


@router.post("/handoff/{sid}/messages")
def applicant_message(sid: str, data: Reply, db: Session = Depends(get_db), user=Depends(get_current_user)):
    owned(db, sid, user)
    if not db.get(OfficerRequest, sid):
        raise HTTPException(409, "Request an officer first.")
    db.add(ChatMessage(session_id=sid, sender="user", message=data.message))
    db.commit()
    return {"sent": True}


@router.get("/admin/consultations")
def queue(db: Session = Depends(get_db), user=Depends(staff)):
    db.merge(OfficerPresence(user_id=user.id, seen_at=datetime.utcnow()))
    db.commit()
    return [{"session_id": r.session_id, "title": s.title, "mine": r.officer_id == user.id,
             "available": r.officer_id is None, "callback": r.callback}
            for r, s in db.query(OfficerRequest, ChatSession).join(ChatSession, ChatSession.id == OfficerRequest.session_id)
            .order_by(ChatSession.created_at.desc())]


@router.post("/admin/consultations/{sid}/claim")
def claim(sid: str, db: Session = Depends(get_db), user=Depends(staff)):
    result = db.execute(update(OfficerRequest).where(OfficerRequest.session_id == sid,
                        OfficerRequest.officer_id.is_(None)).values(officer_id=user.id))
    db.commit()
    current = db.get(OfficerRequest, sid)
    if not current or (not result.rowcount and current.officer_id != user.id):
        raise HTTPException(409, "Conversation unavailable.")
    return transcript(db, sid)


@router.post("/admin/consultations/{sid}/messages")
def reply(sid: str, data: Reply, db: Session = Depends(get_db), user=Depends(staff)):
    request = db.get(OfficerRequest, sid)
    if not request or request.officer_id != user.id:
        raise HTTPException(403, "Claim this conversation first.")
    db.add(ChatMessage(session_id=sid, sender="operator", message=data.message))
    db.commit()
    return {"sent": True}


@router.delete("/admin/consultations/{sid}")
def finish(sid: str, db: Session = Depends(get_db), user=Depends(staff)):
    request = db.get(OfficerRequest, sid)
    if not request or request.officer_id != user.id:
        raise HTTPException(403, "Only the assigned officer can close this consultation.")
    db.get(ChatSession, sid).status = "closed"
    db.delete(request)
    db.commit()
    return {"closed": True}


@router.post("/feedback", status_code=201)
def rate(data: Rating, db: Session = Depends(get_db), user=Depends(get_current_user)):
    owned(db, data.session_id, user)
    db.add(SessionRating(**data.model_dump()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This conversation has already been rated.")
    return {"saved": True}


@router.get("/admin/feedback")
def feedback(db: Session = Depends(get_db), user=Depends(staff)):
    count, average = db.query(func.count(SessionRating.session_id), func.avg(SessionRating.score)).one()
    low = db.query(SessionRating).filter(SessionRating.score <= 2).all()
    return {"count": count, "average": average, "review": [
        {"score": r.score, "comment": r.comment, "session_id": r.session_id, "transcript": transcript(db, r.session_id)} for r in low]}


@router.put("/admin/consultation-threshold")
def threshold(data: Threshold, db: Session = Depends(get_db), user=Depends(staff)):
    db.merge(ConsultationSetting(key="confidence", value=data.value))
    db.commit()
    return data
