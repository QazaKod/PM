import re
from app.services.program_choices import career, LANGS
from app.database import load_programs


def career_answer(message, lang):
    if not re.search(r"career|salary|internship|where can i work|карьер|зарплат|стажиров|кем.*работ|мансап|жалақы|тағылымдама", message, re.I):
        return None
    for program in sorted(load_programs(), key=lambda p: len(p["name"]), reverse=True):
        names = [program["name"], *(program.get("aliases") or [])]
        if any(name and name.casefold() in message.casefold() for name in names):
            data = career(program, lang)
            answer = "\n".join(filter(None, [data["program"], data["roles"], data["statistics"], data["source"], data["career_center"]]))
            return dict(answer=answer, confident=True, matched_id=program["id"], source="career")
    return None


def language_for(message, selected):
    if selected in LANGS:
        return selected
    if re.search("[әіңғүұқөһ]", message, re.I):
        return "kk"
    return "ru" if re.search("[а-яё]", message, re.I) else "en"


def localized_response(result, message, lang):
    i = LANGS.index(lang)
    source = result.get("source")
    if not result.get("confident") and not source:
        routes = [
            (r"career|internship|карьер|мансап", "career@sdu.edu.kz"),
            (r"alumni|выпускник|түлек", "alumni@sdu.edu.kz"),
            (r"billing|payment|accounting|оплат|төлем", "accounting@sdu.edu.kz"),
            (r"technical|portal|технич|портал", "https://helpdesk.sdu.edu.kz"),
        ]
        contact = next((contact for pattern, contact in routes if re.search(pattern, message, re.I)), None)
        intro = ("I could not verify an answer.", "Мне не удалось подтвердить ответ.", "Жауапты растай алмадым.")[i]
        route = ("Contact the relevant department", "Обратитесь в профильный отдел", "Тиісті бөлімге хабарласыңыз")[i] if contact else (
            "No specific department was identified. Contact Admissions", "Профильный отдел не определён. Обратитесь в приёмную комиссию",
            "Тиісті бөлім анықталмады. Қабылдау комиссиясына хабарласыңыз")[i]
        result["answer"] = f"{intro} {route}: {contact or 'admission@sdu.edu.kz'}"
    elif source == "program" and lang != "en":
        p = next((x for x in load_programs() if x["id"] == result.get("matched_id")), None)
        if p:
            labels = ("Срок обучения (лет)", "Стоимость в год (KZT)", "Предметы ЕНТ") if lang == "ru" else ("Оқу мерзімі (жыл)", "Жылдық оқу ақысы (KZT)", "ҰБТ пәндері")
            result["answer"] = f"{p['name']} ({p['code']})\n{labels[0]}: {p['duration_years']}\n{labels[1]}: {p['approx_cost_per_year_kzt']}\n{labels[2]}: {', '.join(p.get('unt_subjects') or [])}"
    elif source == "faq" and lang != "en" and not re.search("[а-яА-Я]", result["answer"]):
        from app.services.faq_translations import translation
        translated = translation(result.get("matched_id"), result["answer"], lang)
        if translated:
            return {**result, "answer": translated}
        notice = ("Проверенный перевод пока недоступен. Ответ на английском:" if lang == "ru" else
                  "Тексерілген аударма әзірге жоқ. Ағылшынша жауап:")
        result["answer"] = notice + "\n" + result["answer"]
    elif result.get("answer") and language_for(result["answer"], None) != lang:
        notice = ("A verified translation is unavailable. The original answer follows.",
                  "Проверенный перевод пока недоступен. Ниже ответ на языке источника.",
                  "Тексерілген аударма әзірге жоқ. Төменде жауап бастапқы тілінде берілген.")[i]
        result["answer"] = notice + "\n" + result["answer"]
    return result
