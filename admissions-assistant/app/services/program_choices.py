"""Program choice tools built from the current admissions catalog."""
import re

from app.database import load_programs

LANGS = ("en", "ru", "kk")
CAREER_CENTER = "https://sdu.edu.kz/en/careers-professional-development/contact-us/"
CAREER_SOURCES = {
    "sdu-is": "https://sdu.edu.kz/en/information-system-example/",
    "sdu-cs": "https://sdu.edu.kz/ru/komputernye-nauki-bakalavr-ru/",
}
ROLES = {
    "cs": ("Software developer, QA engineer", "Разработчик ПО, инженер QA", "Бағдарламашы, QA инженері"),
    "is": ("Systems analyst, database administrator", "Системный аналитик, администратор баз данных", "Жүйелік талдаушы, дерекқор әкімшісі"),
    "se": ("Software engineer, application developer", "Инженер ПО, разработчик приложений", "Бағдарламалық жасақтама инженері, қолданба әзірлеуші"),
    "mcm": ("Modeling engineer, data analyst", "Инженер по моделированию, аналитик данных", "Модельдеу инженері, деректер талдаушысы"),
    "fin": ("Financial analyst, risk analyst", "Финансовый аналитик, риск-аналитик", "Қаржы талдаушысы, тәуекел талдаушысы"),
    "acc": ("Accountant, auditor", "Бухгалтер, аудитор", "Бухгалтер, аудитор"),
    "mgmt": ("Project coordinator, operations manager", "Координатор проектов, операционный менеджер", "Жоба үйлестірушісі, операциялық менеджер"),
    "mkt": ("Marketing analyst, campaign manager", "Маркетолог, менеджер кампаний", "Маркетинг талдаушысы, науқан менеджері"),
    "law": ("Legal adviser, compliance specialist", "Юрисконсульт, специалист по комплаенсу", "Заң кеңесшісі, комплаенс маманы"),
    "ilaw": ("International legal adviser", "Юрист по международному праву", "Халықаралық құқық кеңесшісі"),
    "ir": ("Policy analyst, international cooperation officer", "Политический аналитик, специалист по международному сотрудничеству", "Саясат талдаушысы, халықаралық ынтымақтастық маманы"),
    "trans": ("Translator, interpreter", "Письменный и устный переводчик", "Жазбаша және ауызша аудармашы"),
    "two-lang": ("Language teacher, curriculum developer", "Преподаватель языков, методист", "Тіл мұғалімі, әдіскер"),
    "journalism": ("Reporter, public relations specialist", "Журналист, специалист по связям с общественностью", "Журналист, қоғаммен байланыс маманы"),
}


def career(program, lang):
    index = LANGS.index(lang)
    roles = ROLES.get(program["id"].removeprefix("sdu-"))
    missing = ("Verified starting salary and employment rate are unavailable.",
               "Подтверждённых данных о стартовой зарплате и доле трудоустройства нет.",
               "Бастапқы жалақы мен жұмысқа орналасу үлесі туралы расталған дерек жоқ.")[index]
    detail = roles[index] if roles else ("Ask the career center.", "Уточните в карьерном центре.", "Мансап орталығына хабарласыңыз.")[index]
    if program["id"] == "sdu-cs":
        missing = ("2025 graduates: 85% employed; median salary 206,624 KZT. School alumni employers include Kaspi and Kolesa Group.",
                   "Выпуск 2025 года: трудоустройство 85%, медианная зарплата 206 624 ₸. Среди работодателей выпускников школы — Kaspi и Kolesa Group.",
                   "2025 жылғы түлектердің 85%-ы жұмысқа орналасты. Медианалық жалақы 206 624 ₸. Мектеп түлектері Kaspi және Kolesa Group компанияларында жұмыс істейді.")[index]
        detail += (" · Beta Career internship or research placement", " · Стажировка или исследовательская практика Beta Career", " · Beta Career тағылымдамасы немесе зерттеу практикасы")[index]
    return {"program": program["name"], "roles": detail, "statistics": missing,
            "source": CAREER_SOURCES.get(program["id"]), "career_center": CAREER_CENTER}


def keywords(value):
    return set(re.findall(r"[^\W_]{3,}", value.lower())) - {"and", "the", "for", "want", "work", "study", "with", "become", "хочу"}


def recommend(interests, background, goals):
    ranked = []
    for program in load_programs():
        roles = ROLES.get(program["id"].removeprefix("sdu-"), ())
        primary = keywords(" ".join([program["name"], *roles, *(program.get("aliases") or [])]))
        secondary = keywords(" ".join([program.get("description") or "", *(program.get("unt_subjects") or [])]))
        score = sum(weight * (2 * len(terms & primary) + len(terms & secondary))
                    for terms, weight in [(keywords(interests), 3), (keywords(background), 1), (keywords(goals), 2)])
        if score:
            ranked.append((score, program["name"], program["id"]))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [{"id": pid, "name": name} for _, name, pid in ranked[:5]]
