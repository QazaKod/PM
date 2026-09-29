import os
from sqladmin import ModelView, BaseView, expose
from .models import Program, FAQ, Requirement

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
                # Read last 300 lines for performance
                lines = f.readlines()[-300:]
                if lines:
                    log_content = "".join(lines)
                
        return await self.templates.TemplateResponse(request, "admin_logs.html", context={"log_content": log_content})
