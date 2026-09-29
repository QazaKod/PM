from sqladmin import ModelView
from .models import Program, FAQ, Requirement

class ProgramAdmin(ModelView, model=Program):
    column_list = [Program.id, Program.code, Program.name, Program.degree, Program.duration_years, Program.approx_cost_per_year_kzt]
    column_searchable_list = [Program.id, Program.code, Program.name]
    name = "Program"
    name_plural = "Programs"
    icon = "fa-solid fa-graduation-cap"

class FAQAdmin(ModelView, model=FAQ):
    column_list = [FAQ.id, FAQ.question]
    column_searchable_list = [FAQ.id, FAQ.question]
    name = "FAQ Entry"
    name_plural = "FAQ Entries"
    icon = "fa-solid fa-circle-question"

class RequirementAdmin(ModelView, model=Requirement):
    column_list = [Requirement.id, Requirement.program_id, Requirement.category, Requirement.level, Requirement.topic, Requirement.status]
    column_searchable_list = [Requirement.program_id]
    name = "Admission Requirement"
    name_plural = "Admission Requirements"
    icon = "fa-solid fa-clipboard-list"
