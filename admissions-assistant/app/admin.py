import os
from starlette.requests import Request
from sqladmin import ModelView, BaseView, expose
from sqladmin.authentication import AuthenticationBackend

from .models import Program, FAQ, Requirement, User, ApplicantProfile, ChatSession
from .db_session import SessionLocal
from .security import verify_password, SECRET_KEY


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        if not username or not password:
            return False

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == str(username).strip().lower()).first()
            if not user or not user.is_active or user.role != "admin":
                return False
            if not verify_password(str(password), user.hashed_password):
                return False

            request.session.update({"user_id": user.id, "email": user.email, "role": user.role})
            return True
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        if not user_id:
            return False
        return True


# ==========================================
# DATABASE SECTION
# ==========================================

class ProgramAdmin(ModelView, model=Program):
    column_list = [Program.id, Program.code, Program.name, Program.degree, Program.duration_years, Program.approx_cost_per_year_kzt]
    column_searchable_list = [Program.id, Program.code, Program.name]
    name = "Program"
    name_plural = "Programs"
    icon = "fa-solid fa-graduation-cap"
    category = "Database"


class FAQAdmin(ModelView, model=FAQ):
    column_list = [FAQ.id, FAQ.question]
    column_searchable_list = [FAQ.id, FAQ.question]
    name = "FAQ Entry"
    name_plural = "FAQ Entries"
    icon = "fa-solid fa-circle-question"
    category = "Database"


class RequirementAdmin(ModelView, model=Requirement):
    column_list = [Requirement.id, Requirement.program_id, Requirement.category, Requirement.level, Requirement.topic, Requirement.status]
    column_searchable_list = [Requirement.program_id]
    name = "Admission Requirement"
    name_plural = "Admission Requirements"
    icon = "fa-solid fa-clipboard-list"
    category = "Database"


# ==========================================
# ACCOUNTS SECTION
# ==========================================

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.full_name, User.role, User.is_active, User.created_at]
    column_searchable_list = [User.email, User.full_name]
    name = "User Account"
    name_plural = "User Accounts"
    icon = "fa-solid fa-users"
    category = "Accounts"


class ApplicantProfileAdmin(ModelView, model=ApplicantProfile):
    column_list = [ApplicantProfile.id, ApplicantProfile.user_id, ApplicantProfile.citizenship, ApplicantProfile.target_degree, ApplicantProfile.unt_score, ApplicantProfile.ielts_score]
    name = "Applicant Profile"
    name_plural = "Applicant Profiles"
    icon = "fa-solid fa-id-card"
    category = "Accounts"


class ChatSessionAdmin(ModelView, model=ChatSession):
    column_list = [ChatSession.id, ChatSession.user_id, ChatSession.title, ChatSession.status, ChatSession.created_at]
    name = "Chat Session"
    name_plural = "Chat Sessions"
    icon = "fa-solid fa-comments"
    category = "Accounts"


# ==========================================
# DEVELOPER SECTION
# ==========================================

class LogsAdmin(BaseView):
    name = "System Logs"
    icon = "fa-solid fa-terminal"
    category = "Developer"

    @expose("/logs", methods=["GET"])
    async def logs_page(self, request):
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.log")
        log_content = "No logs recorded yet. Interact with the chat to generate logs."

        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-300:]
                if lines:
                    log_content = "".join(lines)

        return await self.templates.TemplateResponse(request, "admin_logs.html", context={"log_content": log_content})
