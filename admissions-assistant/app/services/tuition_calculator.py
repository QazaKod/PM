"""US19: Tuition & Grant Calculator Service.

Calculates tuition fees, applied scholarship discounts, semester payment schedules,
and state grant probability assessments based on program and UNT score.
"""
from typing import Dict, List, Any, Optional
from app.database import load_programs


DISCOUNT_RULES = {
    "altyn_belgi": {
        "title": "Знак «Алтын белгі»",
        "description": "Скидка 15% для выпускников школ, награжденных знаком «Алтын белгі».",
        "default_percent": 15
    },
    "high_unt": {
        "title": "Высокий балл ЕНТ",
        "description": "Скидка 20% (110–119 баллов) или 30% (120+ баллов) по результатам ЕНТ.",
        "default_percent": 0
    },
    "sibling": {
        "title": "Семейная скидка (Siblings)",
        "description": "Скидка 10% при одновременном обучении двух и более членов одной семьи в SDU.",
        "default_percent": 10
    },
    "spt_winner": {
        "title": "Призер олимпиады SDU SPT",
        "description": "Скидка 30% для призеров Республиканской олимпиады SDU Proficiency Test.",
        "default_percent": 30
    }
}

REGISTRATION_FEE_KZT = 60000


def evaluate_state_grant(program: Dict[str, Any], unt_score: Optional[int]) -> Dict[str, Any]:
    """Evaluate Republic of Kazakhstan State Grant admission probability.

    Historical cutoffs:
    - IT programs (cutoff ~115): unt_score >= 115 -> 'high', 100-114 -> 'medium', < 100 -> 'low'
    - Business programs (cutoff ~105): unt_score >= 105 -> 'high', 90-104 -> 'medium', < 90 -> 'low'
    - Law/Humanities (cutoff ~110): unt_score >= 110 -> 'high', 95-109 -> 'medium', < 95 -> 'low'
    """
    pid = program.get("id", "").lower()
    fac = program.get("faculty", "").lower()

    if pid in ("sdu-cs", "sdu-is", "sdu-se"):
        cutoff = 115
        field_type = "IT / Computer Engineering"
    elif "business" in fac or pid in ("sdu-fin", "sdu-acc", "sdu-mgmt", "sdu-mkt"):
        cutoff = 105
        field_type = "Business & Economics"
    else:
        cutoff = 110
        field_type = "Law & Humanities"

    if unt_score is None:
        return {
            "chance": None,
            "estimated_cutoff": cutoff,
            "field_type": field_type,
            "score": None,
            "description": (
                f"Для оценки вероятности государственного гранта укажите ваш балл ЕНТ. "
                f"Ориентировочный проходной порог для направления «{field_type}»: ~{cutoff} баллов."
            )
        }

    if field_type == "IT / Computer Engineering":
        if unt_score >= 115:
            chance = "high"
            desc = f"Высокая вероятность гранта (ваш балл {unt_score} >= ориентира {cutoff})."
        elif unt_score >= 100:
            chance = "medium"
            desc = f"Средняя вероятность гранта (ваш балл {unt_score}, ориентир ~{cutoff})."
        else:
            chance = "low"
            desc = f"Низкая вероятность госгранта (ваш балл {unt_score} ниже диапазона конкурса ~{cutoff}). Рекомендуется участие в SPT или платное отделение."
    elif field_type == "Business & Economics":
        if unt_score >= 105:
            chance = "high"
            desc = f"Высокая вероятность гранта (ваш балл {unt_score} >= ориентира {cutoff})."
        elif unt_score >= 90:
            chance = "medium"
            desc = f"Средняя вероятность гранта (ваш балл {unt_score}, ориентир ~{cutoff})."
        else:
            chance = "low"
            desc = f"Низкая вероятность госгранта (ваш балл {unt_score} ниже диапазона конкурса ~{cutoff})."
    else:
        if unt_score >= 110:
            chance = "high"
            desc = f"Высокая вероятность гранта (ваш балл {unt_score} >= ориентира {cutoff})."
        elif unt_score >= 95:
            chance = "medium"
            desc = f"Средняя вероятность гранта (ваш балл {unt_score}, ориентир ~{cutoff})."
        else:
            chance = "low"
            desc = f"Низкая вероятность госгранта (ваш балл {unt_score} ниже диапазона конкурса ~{cutoff})."

    return {
        "chance": chance,
        "estimated_cutoff": cutoff,
        "field_type": field_type,
        "score": unt_score,
        "description": desc
    }


def calculate_tuition_and_grant(
    program_id: str,
    unt_score: Optional[int] = None,
    discounts: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Calculate annual/total tuition fee, applied discounts, semester schedule, and grant chance.

    Args:
        program_id: Unique program identifier (e.g. 'sdu-cs', 'sdu-fin')
        unt_score: Optional UNT score (0 to 140)
        discounts: List of discount codes (e.g. ['altyn_belgi', 'high_unt', 'sibling', 'spt_winner'])

    Returns:
        Structured calculation dictionary.
    """
    if unt_score is not None and (unt_score < 0 or unt_score > 140):
        raise ValueError("UNT score must be between 0 and 140 points.")

    all_programs = load_programs()
    # Case-insensitive lookup by id, code, or exact name
    target_clean = program_id.strip().lower()
    program = next(
        (p for p in all_programs if p["id"].lower() == target_clean or (p.get("code") and p["code"].lower() == target_clean) or p["name"].lower() == target_clean),
        None
    )

    if not program:
        raise ValueError(f"Program with id '{program_id}' was not found in the SDU catalog.")

    base_annual_fee = int(program.get("approx_cost_per_year_kzt") or 1500000)
    duration_years = int(program.get("duration_years") or 4)
    base_total_fee = base_annual_fee * duration_years

    # Process discounts
    discounts = discounts or []
    normalized_discounts = [d.strip().lower() for d in discounts]

    applied_discounts = []
    total_raw_percent = 0

    for disc_key in normalized_discounts:
        if disc_key == "altyn_belgi":
            rule = DISCOUNT_RULES["altyn_belgi"]
            percent = 15
            applied_discounts.append({
                "code": "altyn_belgi",
                "title": rule["title"],
                "percentage": percent,
                "description": rule["description"]
            })
            total_raw_percent += percent

        elif disc_key == "high_unt":
            rule = DISCOUNT_RULES["high_unt"]
            if unt_score is not None:
                if unt_score >= 120:
                    percent = 30
                    desc = f"Скидка 30% за результат ЕНТ 120+ баллов ({unt_score} баллов)."
                elif unt_score >= 110:
                    percent = 20
                    desc = f"Скидка 20% за результат ЕНТ 110–119 баллов ({unt_score} баллов)."
                else:
                    percent = 0
                    desc = f"Балл ЕНТ ({unt_score}) недостаточен для получения скидки за высокий балл (требуется от 110)."
            else:
                percent = 0
                desc = "Балл ЕНТ не указан; скидка за высокий балл не начислена."

            if percent > 0:
                applied_discounts.append({
                    "code": "high_unt",
                    "title": rule["title"],
                    "percentage": percent,
                    "description": desc
                })
                total_raw_percent += percent

        elif disc_key == "sibling":
            rule = DISCOUNT_RULES["sibling"]
            percent = 10
            applied_discounts.append({
                "code": "sibling",
                "title": rule["title"],
                "percentage": percent,
                "description": rule["description"]
            })
            total_raw_percent += percent

        elif disc_key == "spt_winner":
            rule = DISCOUNT_RULES["spt_winner"]
            percent = 30
            applied_discounts.append({
                "code": "spt_winner",
                "title": rule["title"],
                "percentage": percent,
                "description": rule["description"]
            })
            total_raw_percent += percent

    # Cap maximum total discount at 50% unless full grant
    is_capped = total_raw_percent > 50
    final_discount_percent = min(total_raw_percent, 50)

    discount_amount_annual = int(round(base_annual_fee * (final_discount_percent / 100.0)))
    discounted_annual_fee = base_annual_fee - discount_amount_annual
    discounted_total_fee = discounted_annual_fee * duration_years
    total_savings_kzt = discount_amount_annual * duration_years

    # Payment schedule: 50% upon enrollment + 50% before spring semester
    semester_1_fee = discounted_annual_fee // 2
    semester_2_fee = discounted_annual_fee - semester_1_fee
    first_payment_total = semester_1_fee + REGISTRATION_FEE_KZT

    grant_assessment = evaluate_state_grant(program, unt_score)

    return {
        "program_id": program["id"],
        "program_code": program.get("code"),
        "program_name": program["name"],
        "faculty": program.get("faculty"),
        "degree": program.get("degree", "Bachelor"),
        "duration_years": duration_years,
        "base_annual_fee": base_annual_fee,
        "base_total_fee": base_total_fee,
        "applied_discounts": applied_discounts,
        "raw_discount_percent": total_raw_percent,
        "total_discount_percent": final_discount_percent,
        "is_discount_capped": is_capped,
        "discount_amount_kzt": discount_amount_annual,
        "discounted_annual_fee": discounted_annual_fee,
        "discounted_total_fee": discounted_total_fee,
        "total_savings_kzt": total_savings_kzt,
        "registration_fee_kzt": REGISTRATION_FEE_KZT,
        "payment_schedule": {
            "semester_1": semester_1_fee,
            "semester_2": semester_2_fee,
            "registration_fee": REGISTRATION_FEE_KZT,
            "first_payment_total": first_payment_total,
            "payment_rules": (
                "50% годовой стоимости оплачивается при зачислении до начала учебного года, "
                "вторые 50% вносятся до начала второго (весеннего) семестра. "
                "Разовый студенческий сбор 60 000 KZT вносится первокурсниками при регистрации."
            )
        },
        "grant_probability": grant_assessment
    }
