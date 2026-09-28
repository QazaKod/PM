"""Deterministic US3 routing. Never infer admission conditions using an LLM.

Context contains only lookup slots, never trusted answers or publication metadata.
It is returned to the caller, so users/tabs/workers cannot share pending requests.
"""
import re
from datetime import date
from urllib.parse import urlparse

from app.database import load_requirements

TOPICS = {
    'exams': r'\b(?:unt|ent|exam\w*|score\w*|points|threshold\w*|test|sat|act|gpa|кт|ент|ұбт)\b|балл|ұпай|емтихан|экзамен|тест|проходн',
    'prerequisites': r'prerequisit|qualification|subject|diploma|degree required|аттестат|диплом|предмет|квалификац|пән|білім|біліктілік',
    'language': r'ielts|toefl|duolingo|english|language|proficiency|англий|язык|ағылшын|тіл|сертификат|certificate',
}
INTENT = r'requirement|eligib|qualify|can i (?:apply|enter|enrol)|admission criteria|требован|услови.*поступ|могу.*поступ|нужно.*поступ|керек|талап|түсу.*шарт'
CATEGORY = {
    'domestic': r'\bdomestic\b|\blocal\b|kazakhstani|казахстан|қазақстан|\brk\b|\bрк\b|\bқр\b|местн|отандық',
    'international': r'\binternational\b|\bforeign\b|иностран|шетел|халықаралық талапкер',
}
LEVEL = {
    'undergraduate': r'undergrad|bachelor|бакалавр',
    'graduate': r'\bgraduate\b|postgrad|master|магистр',
}
TEXT = {
 'en': {
  'program': 'Which program? Please give one exact name or code. Requirements for an unknown program are unavailable; I will not use another program’s requirements.',
  'category': 'Are you a domestic (Kazakhstan) or international applicant?',
  'level': 'Undergraduate (bachelor) or graduate (master)?',
  'published': 'Published, verified', 'missing': 'Requirements unavailable.',
  'unverified': 'Current requirements have not been verified.', 'outdated': 'Requirements are outdated; values are withheld until re-verification.',
  'under_review': 'Requirements are under review and are not yet approved.',
  'notification': 'Automatic availability notifications are not implemented. No subscription has been created. Please check this chat or the official source again.',
  'exams': 'Examinations / scores', 'prerequisites': 'Subjects / qualifications', 'language': 'Language proficiency',
  'domestic': 'Domestic (Kazakhstan)', 'international': 'International', 'undergraduate': 'Undergraduate', 'graduate': 'Graduate',
  'source': 'Official source', 'checked': 'Checked', 'period': 'Admission period', 'review': 'Recheck by',
  'scope': 'Only the selected program, category and level are covered. These are individual verified conditions, not a complete admission decision.',
 },
 'ru': {
  'program': 'Уточните одну программу: точное название или код. Для неизвестной программы требования недоступны; условия другой программы не подставляются.',
  'category': 'Вы местный абитуриент (Казахстан) или иностранный?',
  'level': 'Какой уровень: бакалавриат или магистратура?',
  'published': 'Опубликовано, проверено', 'missing': 'Требования недоступны.',
  'unverified': 'Актуальные требования не подтверждены.', 'outdated': 'Требования устарели; значения скрыты до повторной проверки.',
  'under_review': 'Требования находятся на рассмотрении и ещё не утверждены.',
  'notification': 'Автоматические уведомления о публикации пока не реализованы. Подписка не создана. Проверьте этот чат или официальный источник позже.',
  'exams': 'Экзамены / баллы', 'prerequisites': 'Предметы / квалификация', 'language': 'Владение языком',
  'domestic': 'Местный абитуриент (Казахстан)', 'international': 'Иностранный абитуриент', 'undergraduate': 'Бакалавриат', 'graduate': 'Магистратура',
  'source': 'Официальный источник', 'checked': 'Дата проверки', 'period': 'Период приёма', 'review': 'Перепроверить до',
  'scope': 'Ответ относится только к выбранным программе, категории и уровню. Это отдельные проверенные условия, а не полное решение о поступлении.',
 },
 'kk': {
  'program': 'Бір бағдарламаның нақты атауын немесе кодын көрсетіңіз. Белгісіз бағдарламаның талаптары қолжетімсіз; басқа бағдарламаның шарттары қолданылмайды.',
  'category': 'Сіз отандық (Қазақстан) әлде шетелдік талапкерсіз бе?',
  'level': 'Қай деңгей: бакалавриат немесе магистратура?',
  'published': 'Жарияланған, тексерілген', 'missing': 'Талаптар қолжетімсіз.',
  'unverified': 'Қолданыстағы талаптар расталмаған.', 'outdated': 'Талаптар ескірген; қайта тексерілгенше мәндер көрсетілмейді.',
  'under_review': 'Талаптар қарастырылуда, әлі бекітілмеген.',
  'notification': 'Жариялау туралы автоматты хабарламалар әзірге іске қосылмаған. Жазылым жасалмады. Кейін осы чатты немесе ресми дереккөзді тексеріңіз.',
  'exams': 'Емтихандар / балдар', 'prerequisites': 'Пәндер / біліктілік', 'language': 'Тіл меңгеру',
  'domestic': 'Отандық талапкер (Қазақстан)', 'international': 'Шетелдік талапкер', 'undergraduate': 'Бакалавриат', 'graduate': 'Магистратура',
  'source': 'Ресми дереккөз', 'checked': 'Тексерілген күні', 'period': 'Қабылдау кезеңі', 'review': 'Қайта тексеру мерзімі',
  'scope': 'Жауап тек таңдалған бағдарламаға, санатқа және деңгейге қатысты. Бұл жеке тексерілген шарттар, қабылдау туралы толық шешім емес.',
 },
}


def language_of(message, previous='en'):
    if message.lower().strip() in ('бакалавриат', 'магистратура'):
        return previous
    if re.search(r'[әғқңөұүһі]|талап|керек', message.lower()):
        return 'kk'
    if re.search(r'[а-яё]', message.lower()):
        return 'ru'
    # Slot-only English replies preserve the original question's language.
    if re.search(r'\b(what|which|how|requirements|do i|can i)\b', message.lower()):
        return 'en'
    return previous


def is_requirements_query(message):
    text = message.lower()
    # US5's document checklist is separate from academic eligibility.
    if re.search(r'documents|документ|құжат', text) and not re.search(r'ielts|toefl|score|балл|ұбт|qualification', text):
        return False
    return bool(re.search(INTENT, text) or any(re.search(p, text) for p in TOPICS.values()))


def _contains(text, alias):
    return bool(re.search(r'(?<!\w)' + re.escape(alias.lower()) + r'(?!\w)', text))


def _program_matches(text, data):
    hits = []
    for pid, p in data.items():
        for alias in [p['name'], *p.get('aliases', []), *filter(None, p.get('codes', {}).values())]:
            if _contains(text, alias):
                hits.append((pid, alias.lower()))
    # "International Law" is not also a match for the shorter alias "Law".
    return sorted({pid for pid, alias in hits if not any(alias != other and alias in other for _, other in hits)})


def _status(field, today, lang):
    if not field:
        return 'missing'
    status = field.get('status', 'unverified')
    if status not in ('published', 'under_review', 'unverified', 'missing'):
        return 'unverified'
    if status != 'published':
        return status
    source = urlparse(field.get('source', ''))
    if source.scheme != 'https' or source.hostname != 'sdu.edu.kz' or not field.get('text', {}).get(lang):
        return 'unverified'
    try:
        verified = date.fromisoformat(field['verified_on'])
        due = date.fromisoformat(field['review_due'])
        valid_until = date.fromisoformat(field['valid_until'])
        if verified > today or due < verified:
            return 'unverified'
        if today > due or today > valid_until or (today - verified).days > 30:
            return 'outdated'
    except (ValueError, KeyError, TypeError):
        return 'unverified'
    return 'published'


def answer_requirements(message, context=None, language=None, *, data=None, today=None):
    data = load_requirements() if data is None else data
    today = today or date.today()
    ctx = dict(context or {})
    text = message.lower().strip()
    lang = language or language_of(message, ctx.get('language', 'en'))
    t = TEXT[lang]
    if ctx and re.search(r'notif|subscribe|уведом|подпис|хабарла|жазыл', text):
        return dict(answer=t['notification'], confident=False, source='requirements', matched_id=ctx.get('program_id'), context=ctx, notification_available=False)
    matches = _program_matches(text, data)
    category_text = text
    for pid in matches:
        for alias in [data[pid]['name'], *data[pid].get('aliases', [])]:
            category_text = re.sub(r'(?<!\w)' + re.escape(alias.lower()) + r'(?!\w)', '', category_text)
    categories = [k for k, pattern in CATEGORY.items() if re.search(pattern, category_text)]
    levels = [k for k, pattern in LEVEL.items() if re.search(pattern, text)]
    for p in data.values():
        for level, code in p.get('codes', {}).items():
            if code and _contains(text, code) and level not in levels:
                levels.append(level)
    intent = is_requirements_query(category_text)
    if not intent and re.search(r'cost|tuition|documents|dorm|оплат|стоимост|документ|жатақхана|құжат', text):
        return None
    slot_reply = bool(matches or categories or levels)
    if not intent and not (ctx and (ctx.get('pending') or slot_reply)):
        return None
    topics = [k for k, pattern in TOPICS.items() if re.search(pattern, category_text)]
    if 'language' in topics and not re.search(r'\b(?:unt|ent|sat|act|gpa|кт|ент|ұбт)\b', category_text):
        topics = [topic for topic in topics if topic != 'exams']
    # A fresh full request must not silently inherit a previous program/category.
    if intent and re.search(INTENT, text):
        ctx = {}
    elif intent and not matches and re.search(r'\b(?:for|about)\s+\w+|для\s+\w+', text):
        ctx.pop('program_id', None)
    ctx.update(language=lang, topics=topics or ctx.get('topics') or list(TOPICS))
    years = re.findall(r'\b20\d{2}\b', text)
    if years:
        ctx['admission_year'] = int(years[0])
    if matches:
        ctx['program_id'] = matches[0] if len(matches) == 1 else None
    # An unrecognized answer to the program clarification cannot choose any default.
    if categories:
        ctx['category'] = categories[0] if len(categories) == 1 else None
    if levels:
        ctx['study_level'] = levels[0] if len(levels) == 1 else None
    result = dict(answer='', confident=False, source='requirements', matched_id=ctx.get('program_id'), context=ctx)
    for slot, key, allowed in [('program_id','program',data), ('category','category',CATEGORY), ('study_level','level',LEVEL)]:
        if ctx.get(slot) not in allowed:
            ctx['pending'] = slot
            result['answer'] = t[key]
            result['requirement_status'] = 'clarification'
            return result
    ctx['pending'] = None
    p = data[ctx['program_id']]
    cat, level = ctx['category'], ctx['study_level']
    fields = p.get('requirements', {}).get(cat, {}).get(level, {})
    code = p.get('codes', {}).get(level)
    lines = [f"**{p['name']}**" + (f' ({code})' if code else ''), f"{t[cat]} · {t[level]}", t['scope']]
    statuses = []
    for topic in ctx['topics']:
        field = fields.get(topic, {})
        status = _status(field, today, lang)
        if ctx.get('admission_year') and not field.get('admission_period', '').startswith(str(ctx['admission_year'])):
            status = 'unverified'
        statuses.append(status)
        lines.append(f"\n{t[topic]} — {t[status]}")
        if status == 'published':
            lines.append(field['text'][lang])
        if field.get('source'):
            lines.append(f"{t['source']}: {field['source']}")
            lines.append(f"{t['checked']}: {field.get('checked_on', '—')} · {t['period']}: {field.get('admission_period', '—')} · {t['review']}: {field.get('review_due', '—')}")
    if 'under_review' in statuses:
        lines.append(t['notification'])
    result.update(answer='\n'.join(lines), confident=all(s == 'published' for s in statuses),
                  requirement_status=statuses[0] if len(set(statuses)) == 1 else 'partial',
                  notification_available=False)
    return result
