"""US18: UNT Eligibility Matcher Service.

Compares user's UNT profile subjects and total score against SDU academic programs:
- Normalizes subject inputs (RU, KZ, EN)
- Checks UNT threshold scores (minimum 50 for general, 65 for pedagogical/social, 75 for law/IT)
- Segregates into eligible programs vs deficit programs
- Evaluates state grant probability for each matched program
"""
import re
from typing import Dict, List, Any, Optional
from app.database import load_programs


# Canonical subject dictionary with multivariant multilingual regex
SUBJECT_ALIASES = {
    "Mathematics": [
        r"матем\w*", r"math\w*", r"математика"
    ],
    "Computer Science": [
        r"информ\w*", r"computer\s*science", r"информатика", r"\bcs\b", r"компьютер\w*"
    ],
    "Physics": [
        r"физик\w*", r"physics"
    ],
    "Geography": [
        r"географ\w*", r"geography"
    ],
    "World History": [
        r"всемирн\w*\s*истори\w*", r"дүние\s*жүзі\s*тарих\w*", r"world\s*history",
        r"\bистори\w*\b", r"\bтарих\b"
    ],
    "Fundamentals of Law": [
        r"основ\w*\s*прав\w*", r"құқық\s*негіз\w*", r"fundamentals\s*of\s*law",
        r"\bправ\w*\b", r"\bқұқық\b", r"\blaw\b"
    ],
    "Foreign Language": [
        r"иностранн\w*\s*язык\w*", r"шет\s*тіл\w*", r"ағылшын\w*", r"foreign\s*language",
        r"english", r"английск\w*"
    ],
    "Creative Exams": [
        r"творческ\w*", r"creative", r"шығармашылық"
    ],
    "Biology": [
        r"биолог\w*", r"biology"
    ],
    "Chemistry": [
        r"хими\w*", r"chemistry"
    ]
}


def normalize_subject(subject_raw: str) -> str:
    """Normalize input subject name in RU, KZ, or EN to standard English title."""
    if not subject_raw:
        return ""
    clean = subject_raw.strip().lower()

    # Direct check against known aliases
    for canonical, patterns in SUBJECT_ALIASES.items():
        for pattern in patterns:
            if re.search(pattern, clean):
                return canonical

    return subject_raw.strip().title()


def get_program_threshold(program_id: str, faculty: str) -> int:
    """Determine minimum UNT admission threshold based on program and regulatory criteria:

    - Minimum 75 for Law and IT programs
    - Minimum 65 for Pedagogical & Social sciences
    - Minimum 50 for General programs (Business School, MCM, etc.)
    """
    pid = program_id.lower()
    fac = faculty.lower()

    # IT Programs (75)
    if pid in ("sdu-cs", "sdu-is", "sdu-se"):
        return 75
    # Law Programs (75)
    if pid in ("sdu-law", "sdu-ilaw"):
        return 75
    # Pedagogical & Social Programs (65)
    if pid in ("sdu-two-lang", "sdu-ir", "sdu-trans") or "education" in fac:
        return 65
    # General / Business / MCM (50)
    return 50


def estimate_grant_chance(program_id: str, faculty: str, score: int) -> Dict[str, Any]:
    """Assess State Grant probability based on UNT score and faculty cutoffs."""
    pid = program_id.lower()
    fac = faculty.lower()

    if pid in ("sdu-cs", "sdu-is", "sdu-se"):
        cutoff = 115
        category = "IT / Computer Engineering"
        if score >= 115:
            chance = "high"
        elif score >= 100:
            chance = "medium"
        else:
            chance = "low"
    elif "business" in fac or pid in ("sdu-fin", "sdu-acc", "sdu-mgmt", "sdu-mkt"):
        cutoff = 105
        category = "Business & Economics"
        if score >= 105:
            chance = "high"
        elif score >= 90:
            chance = "medium"
        else:
            chance = "low"
    else:
        cutoff = 110
        category = "Law & Humanities"
        if score >= 110:
            chance = "high"
        elif score >= 95:
            chance = "medium"
        else:
            chance = "low"

    return {
        "chance": chance,
        "estimated_cutoff": cutoff,
        "category": category
    }


def match_unt_eligibility(
    subject_1: str,
    subject_2: str,
    score: int
) -> Dict[str, Any]:
    """Find all SDU programs matching two UNT profile subjects and evaluate score eligibility.

    Args:
        subject_1: First profile subject (e.g. 'Математика', 'Mathematics')
        subject_2: Second profile subject (e.g. 'Информатика', 'Computer Science')
        score: Total UNT score (0 to 140)

    Returns:
        Dict containing:
        - eligible_programs
        - deficit_programs
        - total_matched
        - status_message
        - subjects_normalized
    """
    if score < 0 or score > 140:
        raise ValueError("UNT score must be between 0 and 140 points.")

    norm_sub1 = normalize_subject(subject_1)
    norm_sub2 = normalize_subject(subject_2)
    user_pair = {norm_sub1.lower(), norm_sub2.lower()}

    all_programs = load_programs()
    eligible_programs = []
    deficit_programs = []

    for prog in all_programs:
        prog_subjects = prog.get("unt_subjects") or []
        prog_pair = {normalize_subject(s).lower() for s in prog_subjects}

        # Check if subject combination matches
        if prog_pair == user_pair:
            min_score = get_program_threshold(prog["id"], prog.get("faculty", ""))
            grant_eval = estimate_grant_chance(prog["id"], prog.get("faculty", ""), score)

            prog_info = {
                "id": prog["id"],
                "code": prog.get("code"),
                "name": prog["name"],
                "faculty": prog.get("faculty"),
                "degree": prog.get("degree", "Bachelor"),
                "min_score": min_score,
                "user_score": score,
                "approx_cost_per_year_kzt": prog.get("approx_cost_per_year_kzt"),
                "unt_subjects": prog_subjects,
                "grant_chance": grant_eval["chance"],
                "grant_cutoff": grant_eval["estimated_cutoff"],
            }

            if score >= min_score:
                prog_info["points_surplus"] = score - min_score
                eligible_programs.append(prog_info)
            else:
                prog_info["points_needed"] = min_score - score
                deficit_programs.append(prog_info)

    total_matched = len(eligible_programs) + len(deficit_programs)

    # Formulate human-friendly status message
    if total_matched == 0:
        status_message = (
            f"По комбинации предметов «{norm_sub1} + {norm_sub2}» образовательных программ "
            f"в бакалавриате SDU не найдено. Проверьте правильность выбора предметов ЕНТ."
        )
    elif len(deficit_programs) == 0:
        status_message = (
            f"Отлично! Ваш балл ({score}) достаточен для поступления на платное отделение "
            f"на все найденные программы ({total_matched})."
        )
    elif len(eligible_programs) == 0:
        min_required = min(p["min_score"] for p in deficit_programs)
        status_message = (
            f"По вашим предметам найдено {total_matched} программ, однако вашего балла ({score}) "
            f"пока недостаточно (минимальный порог — {min_required} баллов). "
            f"Вам необходимо набрать еще от {min_required - score} баллов."
        )
    else:
        status_message = (
            f"По вашим предметам найдено {total_matched} программ: вы проходите по баллам на "
            f"{len(eligible_programs)}, а для {len(deficit_programs)} программ вам не хватает баллов."
        )

    return {
        "score": score,
        "subjects_normalized": [norm_sub1, norm_sub2],
        "total_matched": total_matched,
        "eligible_programs": eligible_programs,
        "deficit_programs": deficit_programs,
        "status_message": status_message
    }
