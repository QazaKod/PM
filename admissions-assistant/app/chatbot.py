"""Rule-based matching engine with AI Fallback and Sprint 3 Admissions Integrations.

Implements:
  - US1 Chat-Program Info: answer questions about educational programs
  - US5 Admission FAQ:      answer common admission questions
  - US3 Requirements:       exact, provenance-gated lookup before similarity matching
  - US7 Admission Guide:    step-by-step admission roadmap (domestic/international)
  - US9 Official Links:     verified university portals, testing center, and social channels
  - US18 UNT Matcher:       academic program matching by UNT profile subjects and threshold scores
  - US19 Tuition Calculator: tuition fee breakdown, scholarship discounts, and grant probabilities

Matching hierarchy:
1. US3 Requirements check strictly for academic admission requirements
2. Sprint 3 Specialized Intent Matchers:
   - US7: Step-by-Step Admission Guide
   - US9: Official Source Links
   - US18: UNT Score Eligibility Matcher
   - US19: Tuition & Grant Calculator
3. Token-overlap scoring on programs (US1) and FAQ (US5)
4. AI Fallback (Gemini with top 3 candidates)
"""
import os
import re
import json
from typing import Dict, List, Optional, Tuple

from app.database import load_programs, load_faq
from app.requirements import answer_requirements, language_of
from app.services.admission_guide import get_admission_guide, GuideUnavailable, TEXT as GUIDE_TEXT
from app.services.official_links import get_official_links
from app.services.unt_calculator import (
    match_unt_eligibility,
    normalize_subject,
    SUBJECT_ALIASES
)
from app.services.tuition_calculator import calculate_tuition_and_grant

# --- AI Fallback Imports ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from google import genai
    from google.genai import types
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False


CONFIDENCE_THRESHOLD = 0.34
FALLBACK_MESSAGE = (
    "I'm not confident I can answer that accurately. "
    "Would you like me to connect you with the admissions office "
    "(admission@sdu.edu.kz)?"
)

_STOPWORDS = {
    # English
    "a", "an", "the", "are", "do", "does", "what", "which", "how",
    "i", "want", "to", "for", "of", "in", "on", "about", "can", "you",
    "me", "my", "please", "tell", "much", "there",
    "at", "by", "from", "with", "any", "some", "have", "has", "had", "will",
    # Russian
    "и", "в", "на", "с", "по", "как", "что", "для", "это", "а", "я", "мне", 
    "меня", "о", "об", "к", "у", "из", "за", "от", "или", "не", "мы", "вы",
    "он", "она", "они", "под", "над", "про", "ли", "же",
    # Kazakh
    "мен", "бұл", "үшін", "және", "қандай", "қалай", "кім", "не", "ол", 
    "біз", "сіз", "олар", "бойынша", "туралы", "ба", "бе", "па", "пе", "ма", "ме"
}


_SYNONYM_MAP = {
    "общага": ["dorm", "accommodation", "общежитие", "жатақхана"],
    "общаге": ["dorm", "accommodation", "общежитие", "жатақхана"],
    "общежитии": ["dorm", "accommodation", "общежитие", "жатақхана"],
    "общежития": ["dorm", "accommodation", "общежитие", "жатақхана"],
    "dormitory": ["dorm", "accommodation"],
    "доки": ["documents", "документы", "admission"],
    "документов": ["documents", "документы"],
    "документам": ["documents", "документы"],
    "айти": ["computer", "science", "software", "engineering"],
    "айтишка": ["computer", "science", "software", "engineering"],
    "кодинг": ["computer", "science", "software", "engineering"],
    "оплатить": ["payment", "tuition", "paid", "оплата"],
    "рассрочка": ["payment", "tuition", "paid", "оплата"],
    "спт": ["spt", "olympiad"],
    "олимпиада": ["spt", "olympiad"],
    "гранты": ["grant", "ministry", "грант"],
    "гранта": ["grant", "ministry", "грант"],
}


def _tokenize(text: str) -> list:
    words = re.findall(r"[a-zA-Zа-яёА-ЯЁәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9]+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _stem_match(q_word: str, target_tokens: list) -> int:
    """Morphological stem & synonym matching for Russian, Kazakh, and English tokens."""
    exact = target_tokens.count(q_word)
    if exact > 0:
        return exact

    # Check domain synonyms
    synonyms = _SYNONYM_MAP.get(q_word)
    if synonyms:
        syn_hits = sum(target_tokens.count(s) for s in synonyms)
        if syn_hits > 0:
            return syn_hits

    # Prefix stem matching for longer inflected words (>= 5 chars)
    if len(q_word) >= 5:
        prefix = q_word[: max(5, len(q_word) - 2)]
        stem_hits = sum(
            1
            for t in target_tokens
            if len(t) >= 5 and (t.startswith(prefix) or q_word.startswith(t[: max(5, len(t) - 2)]))
        )
        return stem_hits

    return 0


def _score(query_tokens: list, target_tokens: list) -> float:
    if not query_tokens or not target_tokens:
        return 0.0
    q_set = set(query_tokens)
    score = 0.0
    for q_word in q_set:
        matches = _stem_match(q_word, target_tokens)
        score += min(matches, 3)
    return score / len(q_set)


def get_scored_programs(message: str) -> List[Tuple[Dict, float]]:
    programs = load_programs()
    q_tokens = _tokenize(message)
    scored = []
    for program in programs:
        aliases = " ".join(program.get("aliases") or [])
        codes_dict = program.get("codes") or {}
        codes = " ".join(filter(None, codes_dict.values()))
        target = f"{program['name']} {program['name']} {program['name']} {program['code']} {program.get('description', '')} {program.get('degree', '')} {aliases} {codes}"
        scored.append((program, _score(q_tokens, _tokenize(target))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


FAQS: Optional[List[Dict]] = None


def reload_faqs() -> List[Dict]:
    global FAQS
    FAQS = load_faq()
    return FAQS


def get_scored_faqs(message: str) -> List[Tuple[Dict, float]]:
    global FAQS
    faq_entries = FAQS if FAQS is not None else load_faq()
    q_tokens = _tokenize(message)
    scored = []
    for entry in faq_entries:
        target = " ".join(entry.get("keywords", [])) + " " + entry.get("question", "")
        scored.append((entry, _score(q_tokens, _tokenize(target))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _program_answer(program):
    answer = (
        f"**{program['name']}** ({program['code']}) - {program['faculty']}\n"
        f"Degree: {program['degree']}, {program['duration_years']} years\n"
        f"Cost: ~{program['approx_cost_per_year_kzt']:,} KZT/year\n"
        f"Format: {program['format']}\n"
        f"Description: {program['description']}"
    )
    return {"answer": answer, "confident": True, "source": "program", "matched_id": program["id"]}


# ==========================================
# SPRINT 3: INTENT MATCHERS & HANDLERS
# ==========================================

GUIDE_PATTERN = re.compile(
    r"(?:пошагов\w*|этап\w*|шаг\w*|инструкци\w*|гайд\w*|дорожн\w*\s*карт\w*|руководств\w*)\s*(?:поступлен\w*|в\s+sdu|в\s+сду|абитуриент\w*)?"
    r"|(?:как|қалай)\s+поступить(?:\s+в\s+sdu|\s+в\s+сду)?"
    r"|admission\s+(?:steps|guide|roadmap|procedure)"
    r"|step[- ]by[- ]step\s+admission"
    r"|how\s+to\s+apply\s+to\s+sdu"
    r"|түсу\s+(?:жол\w*|қадам\w*|кезең\w*|нұсқау\w*)"
    r"|қалай\s+түсуге\s+болады"
    r"|қабылдау\s+(?:нұсқаулығы|қадамдары|кезеңдері)",
    re.IGNORECASE
)

LINKS_PATTERN = re.compile(
    r"официальн\w*\s*(?:ссылк\w*|сайт\w*|ресурс\w*|источник\w*)"
    r"|список\s+(?:официальных\s+)?ссылок"
    r"|полезн\w*\s+ссылк\w*"
    r"|ссылк\w*\s*(?:на\s+портал|на\s+сайт|сду|приемн\w*|sdu)"
    r"|official\s+(?:source\s+)?links"
    r"|verified\s+links"
    r"|admissions\s+links"
    r"|useful\s+links"
    r"|ресми\s+сілтемелер"
    r"|пайдалы\s+сілтемелер",
    re.IGNORECASE
)

UNT_KEYWORD_PATTERN = re.compile(
    r"unt\s*matcher|калькулятор\s*ент|подбор\s*программ(?:\s*по\s*ент)?|пройду\s*ли\s*(?:я\s*)?(?:с|по|на)\b|с\s*какими\s*баллами|куда\s*поступить\s*с",
    re.IGNORECASE
)

TUITION_CALC_PATTERN = re.compile(
    r"калькулятор\s*(?:стоимост\w*|оплат\w*|грант\w*)|рассчит\w*\s*стоимост\w*|расчет\s*стоимост\w*|tuition\s*calculator|calculate\s*tuition|скидк\w*\s*(?:алтын\s*белг\w*|семейн\w*|spt|спт|за\s*ент)|вероятност\w*\s*гранта",
    re.IGNORECASE
)


def _handle_admission_guide(message: str, context: Optional[dict] = None, language: Optional[str] = None) -> Optional[Dict]:
    """Recognize inquiries about admission procedure and return structured roadmap."""
    if not GUIDE_PATTERN.search(message):
        return None

    ctx = context or {}
    text = message.lower()
    lang = language or language_of(message, ctx.get("language", "en"))
    from app.database import load_requirements
    from app.requirements import _program_matches
    programs = load_requirements()
    matches = _program_matches(text, programs)
    if len(matches) > 1:
        clarification = {
            'ru': 'Выберите одну программу для гида поступления.',
            'kk': 'Қабылдау нұсқаулығы үшін бір бағдарламаны таңдаңыз.',
            'en': 'Please select one program for the admission guide.',
        }
        return {"answer": clarification[lang], "confident": False, "source": "admission_guide"}
    program_id = matches[0] if matches else ctx.get("program_id")
    # Program names such as International Law are not applicant categories.
    route_text = text
    for pid in matches:
        for alias in [programs[pid]['name'], *programs[pid].get('aliases', [])]:
            route_text = re.sub(r'(?<!\w)' + re.escape(alias.lower()) + r'(?!\w)', '', route_text)
    category = ctx.get("category") or "domestic"
    if re.search(r"иностран|шетел|foreign|international", route_text):
        category = "international"
    elif re.search(r"граждан\w*\s+рк|отандық|domestic|казахстан", route_text):
        category = "domestic"
    level = ctx.get("study_level") or "undergraduate"
    if re.search(r"бакалавр|bachelor|\bundergraduate\b", route_text):
        level = "undergraduate"
    elif re.search(r"магистр|магист|master|\bgraduate\b|postgrad", route_text):
        level = "graduate"
    try:
        guide = get_admission_guide(category=category, level=level, lang=lang, program_id=program_id)
    except GuideUnavailable:
        return {"answer": GUIDE_TEXT[lang]['unavailable'], "confident": False, "source": "admission_guide"}
    except ValueError:
        message = {
            'ru': 'Выбранная программа не соответствует уровню обучения или недоступна. Выберите программу и уровень в разделе «Гид поступления».',
            'kk': 'Таңдалған бағдарлама оқу деңгейіне сәйкес келмейді немесе қолжетімсіз. Нұсқаулықтан бағдарлама мен деңгейді таңдаңыз.',
            'en': 'The selected program does not match this study level or is unavailable. Select a program and level in the Admission Guide.',
        }
        return {"answer": message[lang], "confident": False, "source": "admission_guide"}
    lang = guide['language']
    step_label, review_label = {'ru': ('Шаг', 'Проверено'), 'kk': ('Қадам', 'Тексерілген'), 'en': ('Step', 'Reviewed')}[lang]
    lines = [f"**{guide['title']}**", guide['notice'],
             f"{review_label}: {guide['verified_on']} · {guide['version']}"]
    if guide['program_note']:
        lines.append(guide['program_note'])
        if guide['program_note_source']:
            lines.append(f"{review_label}: {guide['program_note_verified_on']} · {guide['program_note_source']}")
    for item in guide['steps']:
        lines.extend([f"**{step_label} {item['step']}: {item['title']}**", item['description']])
        if item['timeline']:
            lines.append(item['timeline'])
        if item['warning']:
            lines.append(item['warning'])
        lines.append(item['source_url'])
    lines.append(guide['official_admissions_portal'])
    return {
        "answer": "\n\n".join(lines), "confident": True, "source": "admission_guide",
        "matched_id": f"guide_{category}_{level}",
        "context": {"category": category, "study_level": level, "language": lang, "program_id": program_id},
    }


def _handle_official_links(message: str, language: Optional[str] = None) -> Optional[Dict]:
    """Recognize inquiries about official links and return verified sources."""
    if not LINKS_PATTERN.search(message):
        return None

    official = get_official_links()
    lines = ["🌐 **Официальные проверенные ресурсы SDU University:**\n"]
    for item in official["links"]:
        desc = f" — {item['description']}" if item.get("description") else ""
        lines.append(f"• [{item['title']}]({item['url']}){desc}")

    lines.append("\n📞 Call-центр SDU: +7 (727) 307 95 65 | WhatsApp: +7 702 000 11 33")
    return {
        "answer": "\n".join(lines).strip(),
        "confident": True,
        "source": "official_links",
        "matched_id": "links"
    }


def _extract_unt_subjects_and_score(message: str) -> Tuple[List[str], Optional[int]]:
    """Extract profile subjects and total UNT score from user message."""
    score = None
    # Match score (0-140)
    score_match = re.search(r"\b(1[0-3]\d|140|[5-9]\d)\b", message)
    if not score_match:
        score_match = re.search(r"\b([1-9]\d|1[0-4]\d)\s*(?:балл\w*|points?|ұпай)?\b", message)
    if score_match:
        try:
            val = int(score_match.group(1))
            if 0 <= val <= 140:
                score = val
        except ValueError:
            pass

    found_subjects = []
    for canonical, patterns in SUBJECT_ALIASES.items():
        if canonical in ("Biology", "Chemistry"):
            continue
        for pat in patterns:
            if re.search(r"\b" + pat + r"\b", message, re.IGNORECASE):
                if canonical not in found_subjects:
                    found_subjects.append(canonical)
                break
    return found_subjects, score


def _handle_unt_matcher(message: str, language: Optional[str] = None) -> Optional[Dict]:
    """Recognize inquiries regarding UNT score and subject matching."""
    has_keyword = bool(UNT_KEYWORD_PATTERN.search(message))
    found_subjects, score = _extract_unt_subjects_and_score(message)

    # Check if a specific program was mentioned instead of two subjects
    all_progs = load_programs()
    mentioned_prog = None
    msg_clean = message.lower()
    for p in all_progs:
        p_name = p["name"].lower()
        if p_name in msg_clean or p["id"].lower() in msg_clean:
            mentioned_prog = p
            break

    if mentioned_prog and len(found_subjects) < 2 and p.get("unt_subjects"):
        found_subjects = [normalize_subject(s) for s in p["unt_subjects"]]

    if not has_keyword and (len(found_subjects) < 2 or score is None):
        return None

    if len(found_subjects) < 2:
        return {
            "answer": (
                "Для подбора программ по ЕНТ укажите два профильных предмета и ваш балл "
                "(например: «Математика и Информатика, 110 баллов» или «География + Математика, 85»). "
                "Также вы можете воспользоваться онлайн-сервисом на портале: https://admissions.sdu.edu.kz"
            ),
            "confident": True,
            "source": "unt_matcher",
            "matched_id": "unt_matcher"
        }

    sub1, sub2 = found_subjects[0], found_subjects[1]
    eval_score = score if score is not None else 75

    try:
        res = match_unt_eligibility(sub1, sub2, eval_score)
    except Exception as e:
        return None

    lines = [
        "🎯 **Результат подбора программ SDU по баллам ЕНТ**",
        f"Предметы: **{res['subjects_normalized'][0]} + {res['subjects_normalized'][1]}** | Балл: **{eval_score}**\n",
        f"{res['status_message']}\n"
    ]

    if res["eligible_programs"]:
        lines.append("✅ **Доступные программы (балл достаточен):**")
        for p in res["eligible_programs"]:
            grant_str = f"шанс на грант: {p['grant_chance'].upper()}" if p.get("grant_chance") else ""
            cost_str = f"~{p['approx_cost_per_year_kzt']:,} KZT/год" if p.get('approx_cost_per_year_kzt') else ""
            lines.append(f"• **{p['name']}** ({p.get('code')}) — Порог: {p['min_score']} б. | {cost_str} ({grant_str})")
        lines.append("")

    if res["deficit_programs"]:
        lines.append("⚠️ **Программы с дефицитом баллов:**")
        for p in res["deficit_programs"]:
            lines.append(f"• **{p['name']}** ({p.get('code')}) — Порог: {p['min_score']} б. (не хватает: **{p['points_needed']}** б.)")
        lines.append("")

    lines.append("🔗 Подать заявление в SDU: https://admissions.sdu.edu.kz")
    return {
        "answer": "\n".join(lines).strip(),
        "confident": True,
        "source": "unt_matcher",
        "matched_id": "unt_matcher"
    }


def _handle_tuition_calculator(message: str, language: Optional[str] = None) -> Optional[Dict]:
    """Recognize inquiries about tuition cost calculations, discounts, and grants."""
    if not TUITION_CALC_PATTERN.search(message):
        return None

    all_progs = load_programs()
    msg_clean = message.lower()
    matched_prog = None
    for p in all_progs:
        p_name = p["name"].lower()
        if p_name in msg_clean or p["id"].lower() in msg_clean:
            matched_prog = p
            break
        for alias in (p.get("aliases") or []):
            if alias.lower() in msg_clean:
                matched_prog = p
                break
        if matched_prog:
            break

    target_pid = matched_prog["id"] if matched_prog else "sdu-cs"

    # Extract discounts
    discounts = []
    if re.search(r"алтын\s*белг|altyn\s*belgi", msg_clean):
        discounts.append("altyn_belgi")
    if re.search(r"семейн|sibling|брат|сестр", msg_clean):
        discounts.append("sibling")
    if re.search(r"\bspt\b|спт|олимпиад", msg_clean):
        discounts.append("spt_winner")

    # Extract score
    score = None
    score_match = re.search(r"\b(1[0-3]\d|140|[5-9]\d)\b", message)
    if score_match:
        try:
            score = int(score_match.group(1))
        except ValueError:
            pass

    if score and score >= 110:
        discounts.append("high_unt")

    try:
        calc = calculate_tuition_and_grant(program_id=target_pid, unt_score=score, discounts=discounts)
    except Exception:
        return None

    lines = [
        "💰 **Калькулятор стоимости обучения и грантов SDU**",
        f"Программа: **{calc['program_name']}** ({calc.get('program_code', '')}) - {calc['faculty']}\n",
        f"• Базовая стоимость: **{calc['base_annual_fee']:,} KZT/год** (за 4 года: {calc['base_total_fee']:,} KZT)",
    ]

    if calc["applied_discounts"]:
        lines.append(f"• Примененные скидки: **{calc['total_discount_percent']}%** (экономия {calc['discount_amount_kzt']:,} KZT/год):")
        for d in calc["applied_discounts"]:
            lines.append(f"  - {d['title']}: {d['percentage']}%")
        if calc["is_discount_capped"]:
            lines.append("  *(Суммарная скидка ограничена максимальным лимитом 50%)*")
        lines.append(f"• Итоговая стоимость со скидкой: **{calc['discounted_annual_fee']:,} KZT/год** (за 4 года: {calc['discounted_total_fee']:,} KZT)")
    else:
        lines.append("• Дополнительные скидки: не применены (действуют скидки Алтын белгі 15%, SPT 30%, Siblings 10%, ЕНТ 110+ до 30%).")

    sched = calc["payment_schedule"]
    lines.append("\n📅 **График оплаты по семестрам:**")
    lines.append(f"• 1-й семестр (при зачислении): **{sched['semester_1']:,} KZT**")
    lines.append(f"• Обязательный разовый сбор первокурсника: **{sched['registration_fee']:,} KZT**")
    lines.append(f"• **Итого к оплате при зачислении:** **{sched['first_payment_total']:,} KZT**")
    lines.append(f"• 2-й семестр (до весеннего семестра): **{sched['semester_2']:,} KZT**")

    gp = calc["grant_probability"]
    lines.append("\n🎓 **Оценка шанса на государственный грант:**")
    lines.append(f"• {gp['description']}")

    return {
        "answer": "\n".join(lines).strip(),
        "confident": True,
        "source": "tuition_calculator",
        "matched_id": calc["program_id"]
    }



DEADLINES_PATTERN = re.compile(
    r"\b(?:дедлайн\w*|мерзім\w*|deadlines?)\b"
    r"|(?:до\s+какого\s+числа|какие\s+сроки|какой\s+срок)\s+(?:прием\w*|подач\w*|документ\w*|регистраци\w*|грант\w*|ент|сдач\w*|зачислен\w*)"
    r"|(?:срок\w*|дата\w*|даты)\s+(?:прием\w*|подач\w*|сдач\w*|зачислен\w*|регистраци\w*|грант\w*|ент)"
    r"|(?:когда\s+(?:заканчивается|завершается|дедлайн|прием|конкурс|подавать|начинается|стартует))\s+(?:прием\w*|подач\w*|документ\w*|грант\w*|ент|жатақхана|общежит\w*|регистраци\w*|зачислен\w*)"
    r"|(?:application|submission|admission|registration)\s+deadline\w*"
    r"|deadline\s+(?:for|to)\s+(?:apply|application|admission|grant|scholarship|dormitory|unt)"
    r"|when\s+is\s+the\s+deadline"
    r"|when\s+does\s+(?:application|admission)\s+(?:close|end|start)"
    r"|(?:құжат\s+тапсыру|өтініш\s+беру|грант|қабылдау|ұбт|жатақхана)\s+(?:мерзімі|мерзімдері|қашан)"
    r"|мерзім\w*\s+қашан",
    re.IGNORECASE
)


def _detect_deadline_language(message: str, language: Optional[str] = None) -> str:
    if language in ("ru", "kk", "en"):
        return language
    msg_lower = message.lower()
    if any(c in msg_lower for c in "әғқңөұүһі") or re.search(r"\b(қашан|мерзімі|құжат|тапсыру|грантқа|түсу)\b", msg_lower):
        return "kk"
    if re.search(r"[а-яё]", msg_lower):
        return "ru"
    return "en"


def _handle_deadlines(message: str, language: Optional[str] = None) -> Optional[Dict]:
    """Recognize inquiries about admissions campaign deadlines and academic dates."""
    if not DEADLINES_PATTERN.search(message):
        return None

    lang = _detect_deadline_language(message, language)
    msg_clean = message.lower()

    category = None
    if re.search(r"грант|grant", msg_clean):
        category = "grant"
    elif re.search(r"ент|unt|тестирован|тестілеу", msg_clean):
        category = "unt"
    elif re.search(r"общежит|dorm|жатақхана|хостел", msg_clean):
        category = "dormitory"
    elif re.search(r"творческ|экзамен|exam|емтихан|психометр", msg_clean):
        category = "exam"
    elif re.search(r"\bspt\b|спт|олимпиад", msg_clean):
        category = "olympiad"
    elif re.search(r"договор|платн|contract|ақылы|оплат|зачислен", msg_clean):
        category = "contract"

    degree_level = None
    if re.search(r"магистр|master|graduate", msg_clean):
        degree_level = "graduate"
    elif re.search(r"бакалавр|bachelor|undergraduate", msg_clean):
        degree_level = "undergraduate"

    from app.services.deadlines import get_all_deadlines
    deadlines = get_all_deadlines(category=category, degree_level=degree_level, lang=lang)

    headers = {
        "ru": "📅 **Официальные ключевые дедлайны приемной кампании SDU 2026-2027:**\n",
        "kk": "📅 **SDU 2026-2027 қабылдау науқанының ресми негізгі мерзімдері:**\n",
        "en": "📅 **Official SDU Admissions Campaign Deadlines (2026-2027 intake):**\n",
    }
    status_badges = {
        "ru": {"active": "🟢 Прием открыт (Активен)", "upcoming": "⏳ Предстоит", "passed": "🔴 Срок завершен"},
        "kk": {"active": "🟢 Қабылдау ашық (Белсенді)", "upcoming": "⏳ Алдағы кезең", "passed": "🔴 Мерзімі аяқталды"},
        "en": {"active": "🟢 Active (Open)", "upcoming": "⏳ Upcoming", "passed": "🔴 Closed / Passed"},
    }
    days_left_labels = {
        "ru": "Осталось дней:",
        "kk": "Қалған күндер:",
        "en": "Days remaining:",
    }

    lines = [headers.get(lang, headers["ru"])]
    for dl in deadlines:
        badge = status_badges.get(lang, status_badges["ru"]).get(dl["status"], dl["status"])
        days_label = days_left_labels.get(lang, days_left_labels["ru"])

        lines.append(f"📌 **{dl['title']}** — {badge}")
        lines.append(f"• **Сроки / Dates:** {dl['date_start']} — {dl['date_end']}")
        if dl["status"] != "passed":
            lines.append(f"• **{days_label}** {dl['days_left']} дн.")
        lines.append(f"• {dl['description']}")
        if dl.get("passed_advice") and dl["status"] == "passed":
            lines.append(f"• 💡 *{dl['passed_advice']}*")
        lines.append(f"• 🔗 [Подробнее / Details]({dl['action_url']})\n")

    portals = {
        "ru": "🌐 Официальный портал подачи заявок: https://app.sdu.edu.kz | Call-центр: +7 (727) 307 95 65",
        "kk": "🌐 Ресми құжат тапсыру порталы: https://app.sdu.edu.kz | Call-орталық: +7 (727) 307 95 65",
        "en": "🌐 Official application portal: https://app.sdu.edu.kz | Admissions Office: +7 (727) 307 95 65",
    }
    lines.append(portals.get(lang, portals["ru"]))

    matched_id = f"deadlines_{category or 'all'}"
    return {
        "answer": "\n".join(lines).strip(),
        "confident": True,
        "source": "deadlines",
        "matched_id": matched_id
    }


def _resolve_followup_program_from_history(
    message: str,
    context: Optional[dict] = None,
    history: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """
    Multi-turn memory: if the user asks a follow-up question about cost, duration, format,
    or description (e.g., 'А какая стоимость?', 'How much does it cost there?') without
    repeating the program name, resolve the program from recent conversation history or context.
    """
    followup_pattern = re.compile(
        r"\b(?:стоимост\w*|сколько\s+стоит|цен\w*|длительност\w*|сколько\s+лет|формат|описани\w*|туда|на\s+не[её]|по\s+ней|it\s+cost|that\s+program|its\s+tuition|its\s+duration|бағасы|қанша\s+тұрады)\b",
        re.IGNORECASE,
    )
    if not followup_pattern.search(message):
        return None

    programs = load_programs()
    # 1. Check explicit context program_id
    ctx = context or {}
    ctx_prog_id = ctx.get("program_id") or ctx.get("last_program_id")
    if ctx_prog_id:
        found = next((p for p in programs if p["id"] == ctx_prog_id), None)
        if found:
            return found

    # 2. Scan recent conversation history (most recent first)
    if history:
        for turn in reversed(history[-6:]):
            text = turn.get("message", "")
            if not text:
                continue
            scored = get_scored_programs(text)
            if scored and scored[0][1] >= CONFIDENCE_THRESHOLD:
                return scored[0][0]
    return None


def get_ai_fallback_response(
    message: str,
    top_programs: list,
    top_faqs: list,
    history: Optional[List[Dict]] = None,
) -> Dict:
    """Uses Gemini API as a smart fallback with top matches and multi-turn conversation history."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not AI_AVAILABLE or not api_key:
        print("AI Fallback skipped: Missing google-genai library or GEMINI_API_KEY")
        return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}
        
    try:
        client = genai.Client(api_key=api_key)
        
        programs_ctx = [{k: v for k, v in p.items() if k != "unt_subjects"} for p in top_programs]
        faq_ctx = [f for f in top_faqs if f["id"] != "faq_language"]
        history_ctx = (history or [])[-6:]
        
        context = (
            "You are a university admissions assistant.\n"
            "If the user is just greeting you (e.g. 'Hello', 'Привет', 'Сәлем') or making small talk, respond warmly and concisely in the same language. "
            "Return a JSON object: {\"source\": \"greeting\", \"answer\": \"Your text\"}.\n\n"
            "Otherwise, select an entry that answers the user's question (taking RECENT_HISTORY into account for follow-up questions). "
            "Return ONLY a JSON object with source (\"program\" or \"faq\") and matched_id, or {} if no entry answers it.\n"
            "Do not author admission conditions yourself.\n"
            f"RECENT_HISTORY: {json.dumps(history_ctx, ensure_ascii=False)}\n"
            f"PROGRAMS: {json.dumps(programs_ctx, ensure_ascii=False)}\n"
            f"FAQ: {json.dumps(faq_ctx, ensure_ascii=False)}"
        )

        config = types.GenerateContentConfig(
            system_instruction=context,
            temperature=0,
            response_mime_type="application/json",
        )
        
        chat = client.chats.create(model='gemini-3.6-flash', config=config)
        response = chat.send_message(message)
        selection = json.loads(response.text)
        
        if selection.get("source") == "greeting":
            return {"answer": selection.get("answer"), "confident": True, "source": "greeting", "matched_id": None}
        if selection.get("source") == "program":
            program = next((p for p in top_programs if p["id"] == selection.get("matched_id")), None)
            if program:
                return _program_answer(program)
        if selection.get("source") == "faq":
            entry = next((f for f in top_faqs if f["id"] == selection.get("matched_id")), None)
            if entry:
                return {"answer": entry["answer"], "confident": True, "source": "faq", "matched_id": entry["id"]}
        return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}
    except Exception as e:
        print(f"AI Fallback Error: {e}")
        return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}


def answer_query(
    message: str,
    context=None,
    language=None,
    history: Optional[List[Dict]] = None,
) -> Dict:
    """Unified entry point (Router). Only ONE decision path."""
    
    # 1. Sprint 3 Specialized Intent Matchers
    # 1.1 US7: Admission Guide
    guide_res = _handle_admission_guide(message, context, language)
    if guide_res is not None:
        return guide_res

    # 1.2 US9: Official Source Links
    links_res = _handle_official_links(message, language)
    if links_res is not None:
        return links_res

    # 1.3 US18: UNT Score Eligibility Matcher
    unt_res = _handle_unt_matcher(message, language)
    if unt_res is not None:
        return unt_res

    # 1.4 US19: Tuition & Grant Calculator
    tuition_res = _handle_tuition_calculator(message, language)
    if tuition_res is not None:
        return tuition_res

    # 1.5 US8: Official Admissions Deadlines & Dates
    deadlines_res = _handle_deadlines(message, language)
    if deadlines_res is not None:
        return deadlines_res

    # 2. US-3 (Saken's logic) - check strictly for requirements
    requirements = answer_requirements(message, context, language)
    if requirements is not None:
        return requirements
        
    # 3. Hybrid Token + Stem + Synonym Matching (US-1 & US-5)
    scored_programs = get_scored_programs(message)
    scored_faqs = get_scored_faqs(message)
    
    best_p, p_score = scored_programs[0] if scored_programs else (None, 0.0)
    best_f, f_score = scored_faqs[0] if scored_faqs else (None, 0.0)

    # 4. Fast Local Response (if confident)
    if p_score >= CONFIDENCE_THRESHOLD and p_score >= f_score:
        return _program_answer(best_p)
    if f_score >= CONFIDENCE_THRESHOLD:
        return {"answer": best_f["answer"], "confident": True, "source": "faq", "matched_id": best_f["id"]}

    # 4.5 Multi-turn follow-up resolution from conversation history
    followup_prog = _resolve_followup_program_from_history(message, context, history)
    if followup_prog is not None:
        return _program_answer(followup_prog)
        
    # 5. AI Fallback (Expanded top-6 RAG candidates + conversation history)
    top_6_programs = [p[0] for p in scored_programs[:6]]
    top_6_faqs = [f[0] for f in scored_faqs[:6]]
    
    return get_ai_fallback_response(message, top_6_programs, top_6_faqs, history=history)
