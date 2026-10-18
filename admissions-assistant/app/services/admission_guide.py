"""US7: reviewed, versioned procedures, reloaded on every request.

The guide offers instructions, not an admissions decision. Expired procedures
are withheld; a past deadline is retained only with an explicit closed warning.
"""
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.database import load_programs, load_requirements
from app.requirements import _status

PROCEDURES_FILE = Path(__file__).resolve().parents[2] / 'data' / 'admission_procedures.json'


class GuideUnavailable(Exception):
    """No safe, reviewed procedure can be served."""


class LocalizedStep(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ProcedureStep(BaseModel):
    id: str = Field(min_length=1, pattern=r'^[a-z0-9_-]+$')
    source_id: str
    text: dict[str, LocalizedStep]
    deadline: date | None = None

    @model_validator(mode='after')
    def translations(self):
        if set(self.text) != {'ru', 'kk', 'en'}:
            raise ValueError('Every step needs RU, KK and EN translations')
        return self


class ProcedureRoute(BaseModel):
    category: Literal['domestic', 'international']
    level: Literal['undergraduate', 'graduate']
    steps: list[ProcedureStep] = Field(min_length=1)
    program_steps: dict[str, list[ProcedureStep]] = Field(default_factory=dict)


class ProcedureSource(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1)
    url: str

    @model_validator(mode='after')
    def official_url(self):
        url = urlparse(self.url)
        if url.scheme != 'https' or url.hostname not in {'sdu.edu.kz', 'admissions.sdu.edu.kz'} or url.username or url.password:
            raise ValueError('An official HTTPS SDU source is required')
        return self


class ProcedureCatalog(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    version: str = Field(min_length=1)
    status: Literal['reviewed']
    verified_on: date
    review_due: date
    sources: dict[str, ProcedureSource]
    routes: list[ProcedureRoute]

    @model_validator(mode='after')
    def integrity(self):
        pairs = [(r.category, r.level) for r in self.routes]
        expected = {(c, l) for c in ('domestic', 'international') for l in ('undergraduate', 'graduate')}
        if len(pairs) != 4 or set(pairs) != expected:
            raise ValueError('Exactly four distinct applicant routes are required')
        if self.review_due < self.verified_on or (self.review_due - self.verified_on).days > 30:
            raise ValueError('Review period must be between 0 and 30 days')
        for route in self.routes:
            variants = [route.steps] + [route.steps + extra for extra in route.program_steps.values()]
            for steps in variants:
                if len({s.id for s in steps}) != len(steps):
                    raise ValueError('Duplicate step ID')
                if any(s.source_id not in self.sources for s in steps):
                    raise ValueError('Missing source')
        return self


def local_today():
    return datetime.now(ZoneInfo('Asia/Almaty')).date()


def load_catalog(path=None, today=None):
    today = today or local_today()
    path = Path(path or os.getenv('ADMISSION_GUIDE_FILE') or PROCEDURES_FILE)
    try:
        catalog = ProcedureCatalog.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValidationError, ValueError) as exc:
        raise GuideUnavailable('Procedure data is missing or invalid; contact admissions.') from exc
    if not catalog.verified_on <= today <= catalog.review_due:
        raise GuideUnavailable('Procedure review has expired or is future-dated; contact admissions.')
    return catalog


TEXT = {
    'ru': {
        'title': 'Пошаговый гид поступления SDU', 'domestic': 'Граждане РК', 'international': 'Иностранные абитуриенты',
        'undergraduate': 'Бакалавриат', 'graduate': 'Магистратура',
        'notice': 'Общий проверенный маршрут. Точные баллы, платежи и условия выбранной программы уточняйте у комиссии. Сроки относятся к конкретному набору; прошедшие даты не открывают новый приём.',
        'master': 'На странице магистратуры есть даты прошлых лет. Актуальные сроки и условия магистратуры необходимо подтвердить у комиссии.',
        'deadline': 'Срок действия: до', 'closed': 'Цикл приёма 2026 закрыт для этого действия',
        'unknown': 'Срок уточните у комиссии до выполнения шага.',
        'program': 'Проверенные специальные условия программы сейчас недоступны. Уточните предметы, пороги и дополнительные испытания у комиссии.',
        'unavailable': 'Проверенный гид временно недоступен. Обратитесь в приёмную комиссию: https://admissions.sdu.edu.kz',
    },
    'kk': {
        'title': 'SDU-ға түсудің қадамдық нұсқаулығы', 'domestic': 'ҚР азаматтары', 'international': 'Шетелдік талапкерлер',
        'undergraduate': 'Бакалавриат', 'graduate': 'Магистратура',
        'notice': 'Тексерілген жалпы жол. Таңдалған бағдарламаның нақты балдарын, төлемдері мен шарттарын комиссиядан анықтаңыз. Мерзімдер нақты қабылдауға қатысты; өткен күндер жаңа қабылдауды ашпайды.',
        'master': 'Магистратура бетінде өткен жылдардың мерзімдері бар. Қазіргі мерзімдер мен шарттарды комиссиядан растау қажет.',
        'deadline': 'Мерзімі:', 'closed': 'Бұл әрекет үшін 2026 қабылдау кезеңі жабық',
        'unknown': 'Қадамды орындамас бұрын мерзімін комиссиядан нақтылаңыз.',
        'program': 'Бағдарламаның тексерілген арнайы шарттары қазір қолжетімсіз. Пәндерді, шекті балдарды және қосымша сынақтарды комиссиядан нақтылаңыз.',
        'unavailable': 'Тексерілген нұсқаулық уақытша қолжетімсіз. Қабылдау комиссиясына хабарласыңыз: https://admissions.sdu.edu.kz',
    },
    'en': {
        'title': 'SDU Step-by-Step Admission Guide', 'domestic': 'Domestic applicants', 'international': 'International applicants',
        'undergraduate': 'Bachelor', 'graduate': 'Master',
        'notice': 'Reviewed general route. Confirm program-specific scores, payments and conditions with admissions. Deadlines are intake-specific; past dates do not open a new intake.',
        'master': 'The master’s page contains dates from earlier years. Confirm current master’s deadlines and conditions with admissions.',
        'deadline': 'Deadline:', 'closed': 'The 2026 admission cycle is closed for this action',
        'unknown': 'Confirm the deadline with admissions before taking this step.',
        'program': 'Reviewed program-specific conditions are unavailable. Confirm subjects, thresholds and additional exams with admissions.',
        'unavailable': 'The reviewed guide is temporarily unavailable. Contact admissions: https://admissions.sdu.edu.kz',
    },
}


def get_admission_guide(category='domestic', level='undergraduate', lang='ru', program_id=None, *, today=None):
    category, level, lang = (v.strip().lower() for v in (category, level, lang))
    lang = {'kz': 'kk', 'kk-kz': 'kk', 'kazakh': 'kk', 'english': 'en', 'en-us': 'en', 'russian': 'ru', 'ru-ru': 'ru'}.get(lang, lang)
    if category not in ('domestic', 'international') or level not in ('undergraduate', 'graduate') or lang not in TEXT:
        raise ValueError('Unsupported category, level or language')
    today = today or local_today()
    catalog = load_catalog(today=today)
    t = TEXT[lang]
    route = next(r for r in catalog.routes if (r.category, r.level) == (category, level))
    program = None
    program_note = None
    program_note_source = None
    program_note_verified_on = None
    if program_id:
        program = next((p for p in load_programs() if p['id'] == program_id), None)
        if program is None:
            raise ValueError('Program not found')
        expected_degree = 'Bachelor' if level == 'undergraduate' else 'Master'
        if program['degree'] != expected_degree:
            raise ValueError('Program degree does not match the selected level')
        requirement = load_requirements().get(program_id, {}).get('requirements', {}).get(category, {}).get(level, {}).get('prerequisites')
        program_note = t['program']
        if _status(requirement, today, lang) == 'published':
            program_note = requirement['text'][lang]
            program_note_source = requirement['source']
            program_note_verified_on = requirement['verified_on']
    steps = []
    # Additional entrance actions precede funding/document submission, rather
    # than appearing only as a note after the generic route.
    route_steps = [route.steps[0], *route.program_steps.get(program_id, []), *route.steps[1:]]
    for index, item in enumerate(route_steps, 1):
        source = catalog.sources[item.source_id]
        closed = item.deadline is not None and item.deadline < today
        steps.append({
            'id': item.id, 'step': index, **item.text[lang].model_dump(),
            'timeline': f"{t['deadline']} {item.deadline.isoformat()}" if item.deadline else None,
            'deadline': item.deadline.isoformat() if item.deadline else None,
            'deadline_status': ('closed' if closed else 'upcoming') if item.deadline else 'confirm',
            'warning': t['closed'] if closed else (t['unknown'] if not item.deadline else None),
            'source_url': source.url, 'source_title': source.title,
        })
    return {
        'category': category, 'level': level, 'language': lang,
        'program_id': program_id, 'program_name': program['name'] if program else None,
        'program_note': program_note,
        'program_note_source': program_note_source,
        'program_note_verified_on': program_note_verified_on,
        'title': f"{t['title']}: {t[category]} · {t[level]}" + (f" · {program['name']}" if program else ''),
        'version': catalog.version, 'verified_on': catalog.verified_on.isoformat(), 'review_due': catalog.review_due.isoformat(),
        'notice': t['notice'] + (' ' + t['master'] if level == 'graduate' else ''),
        'total_steps': len(steps), 'steps': steps,
        'official_admissions_portal': 'https://admissions.sdu.edu.kz',
        'contacts': {'email': 'admissions@sdu.edu.kz' if category == 'domestic' else 'intadmissions@sdu.edu.kz'},
    }
