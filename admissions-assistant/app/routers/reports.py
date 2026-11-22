from collections import Counter
from datetime import date, datetime, time
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.db_session import get_db
from app.models import User, Program, ChatMessage, SavedProgram
from app.security import require_role

router = APIRouter(tags=["Staff reports"])


def period(query, column, start, end):
    if start:
        query = query.filter(column >= datetime.combine(start, time.min))
    if end:
        query = query.filter(column <= datetime.combine(end, time.max))
    return query


@router.get("/admin/reports/{kind}.xlsx")
def export(kind: Literal["applicants", "programs"], start: date | None = None, end: date | None = None,
           user=Depends(require_role(["admin", "manager"])), db: Session = Depends(get_db)):
    if start and end and start > end:
        raise HTTPException(422, "Start date must precede end date.")
    book = Workbook()
    sheet = book.active
    sheet.title = kind.capitalize()
    if kind == "applicants":
        sheet.append(["Name", "Email", "Phone", "Verified", "Registered (UTC)"])
        for applicant in period(db.query(User).filter_by(role="applicant"), User.created_at, start, end).order_by(User.id):
            sheet.append([applicant.full_name, applicant.email, applicant.phone, applicant.is_verified, applicant.created_at])
    else:
        sheet.append(["Program", "Faculty", "Bookmarks", "Program inquiries"])
        bookmarks = Counter(row.program_id for row in period(db.query(SavedProgram).join(User).filter(User.role == "applicant"),
                                                              SavedProgram.created_at, start, end))
        inquiries = Counter()
        for message in period(db.query(ChatMessage).filter_by(sender="bot", source="program"), ChatMessage.timestamp, start, end):
            key = (message.context_state or {}).get("program_id")
            if key:
                inquiries[key] += 1
        programs = db.query(Program).order_by(Program.faculty, Program.name).all()
        for program in programs:
            sheet.append([program.name, program.faculty, bookmarks[program.id], inquiries[program.id]])
        sheet.append(["Total", None, sum(bookmarks[p.id] for p in programs), sum(inquiries[p.id] for p in programs)])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        header = column[0]
        header.font = Font(bold=True, color="FFFFFF")
        header.fill = PatternFill("solid", fgColor="185D62")
        sheet.column_dimensions[get_column_letter(header.column)].width = min(60, max(15, max(len(str(c.value or "")) for c in column) + 2))
        for cell in column[1:]:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{kind}-{date.today()}.xlsx"', "Cache-Control": "no-store"})
