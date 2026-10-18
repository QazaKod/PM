"""Sprint 3 Admissions & Calculators Test Suite.

Covers:
- US7: Step-by-Step Admission Guide
- US9: Official Source Links
- US18: UNT Eligibility Matcher
- US19: Tuition & Grant Calculator
- API Router Endpoints (/admissions/*)
- Chatbot Integration for Sprint 3 User Stories
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import chatbot
from app.services.admission_guide import get_admission_guide
from app.services.official_links import get_official_links
from app.services.unt_calculator import match_unt_eligibility, normalize_subject
from app.services.tuition_calculator import calculate_tuition_and_grant

client = TestClient(app)


# ==========================================
# US7: ADMISSION GUIDE TESTS
# ==========================================

def test_us7_admission_guide_default_domestic_undergraduate():
    guide = get_admission_guide()
    assert guide["category"] == "domestic"
    assert guide["level"] == "undergraduate"
    assert guide["language"] == "ru"
    assert guide["total_steps"] == 6
    assert len(guide["steps"]) == 6

    # Verify Step contents
    steps = guide["steps"]
    assert "ЕНТ" in steps[0]["title"]
    assert "грант" in steps[1]["title"].lower() or "spt" in steps[1]["title"].lower()
    assert "подача документов" in steps[2]["title"].lower()
    assert "английского" in steps[3]["title"].lower() or "ielts" in steps[3]["title"].lower()
    assert "договор" in steps[4]["title"].lower() or "взноса" in steps[4]["title"].lower()
    assert "общежитие" in steps[5]["title"].lower() or "portal" in steps[5]["title"].lower()


def test_us7_admission_guide_localized_versions():
    guide_kk = get_admission_guide(category="domestic", level="undergraduate", lang="kk")
    assert guide_kk["language"] == "kk"
    assert "ҰБТ" in guide_kk["steps"][0]["title"]

    guide_en = get_admission_guide(category="domestic", level="undergraduate", lang="en")
    assert guide_en["language"] == "en"
    assert "UNT" in guide_en["steps"][0]["title"]


def test_us7_admission_guide_international():
    guide = get_admission_guide(category="international", level="undergraduate", lang="ru")
    assert guide["category"] == "international"
    assert guide["total_steps"] == 6
    # International applicants are exempt from UNT
    assert "виз" in guide["steps"][3]["title"].lower() or "виз" in guide["steps"][3]["description"].lower()


def test_us7_admission_guide_api_endpoint():
    response = client.get("/admissions/guide?category=domestic&level=undergraduate&lang=ru")
    assert response.status_code == 200
    data = response.json()
    assert data["total_steps"] == 6
    assert data["official_admissions_portal"] == "https://admissions.sdu.edu.kz"


# ==========================================
# US9: OFFICIAL SOURCE LINKS TESTS
# ==========================================

def test_us9_official_links_service():
    links_data = get_official_links()
    assert links_data["verified"] is True
    assert links_data["total"] >= 8

    urls = links_data["urls"]
    assert urls["sdu_portal"] == "https://sdu.edu.kz"
    assert urls["admissions_portal"] == "https://admissions.sdu.edu.kz"
    assert urls["testcenter"] == "https://testcenter.kz"
    assert urls["egov"] == "https://egov.kz"
    assert urls["sdu_spt"] == "https://spt.sdu.edu.kz"
    assert urls["whatsapp_admissions"] == "https://wa.me/77020001133"
    assert urls["telegram_bot"] == "https://t.me/sdu_admissions_registration_bot"
    assert urls["dormitory"] == "https://sdu.edu.kz/dormitory"


def test_us9_official_links_api_endpoint():
    response = client.get("/admissions/links")
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert len(data["links"]) >= 8


# ==========================================
# US18: UNT ELIGIBILITY MATCHER TESTS
# ==========================================

def test_us18_normalize_subject():
    assert normalize_subject("Математика") == "Mathematics"
    assert normalize_subject("Информатика") == "Computer Science"
    assert normalize_subject("физика") == "Physics"
    assert normalize_subject("География") == "Geography"
    assert normalize_subject("Всемирная история") == "World History"
    assert normalize_subject("Основы права") == "Fundamentals of Law"
    assert normalize_subject("Иностранный язык") == "Foreign Language"


def test_us18_unt_matcher_it_eligible():
    # Math + CS with 110 points -> should match CS, IS, SE as eligible
    result = match_unt_eligibility(
        subject_1="Математика",
        subject_2="Информатика",
        score=110
    )
    assert result["total_matched"] == 3
    assert len(result["eligible_programs"]) == 3
    assert len(result["deficit_programs"]) == 0

    matched_ids = [p["id"] for p in result["eligible_programs"]]
    assert "sdu-cs" in matched_ids
    assert "sdu-is" in matched_ids
    assert "sdu-se" in matched_ids

    # For 110 points, threshold is 75, points_surplus = 35
    for p in result["eligible_programs"]:
        assert p["points_surplus"] == 35


def test_us18_unt_matcher_it_deficit():
    # Math + CS with 60 points -> threshold is 75, points_needed = 15
    result = match_unt_eligibility(
        subject_1="Mathematics",
        subject_2="Computer Science",
        score=60
    )
    assert result["total_matched"] == 3
    assert len(result["eligible_programs"]) == 0
    assert len(result["deficit_programs"]) == 3

    for p in result["deficit_programs"]:
        assert p["points_needed"] == 15


def test_us18_unt_matcher_other_combinations():
    # Math + Physics -> MCM
    res_mcm = match_unt_eligibility("Математика", "Физика", 65)
    assert any(p["id"] == "sdu-mcm" for p in res_mcm["eligible_programs"])

    # Math + Geography -> Finance, Accounting, Management, Marketing
    res_biz = match_unt_eligibility("Математика", "География", 70)
    assert res_biz["total_matched"] >= 4
    biz_ids = [p["id"] for p in res_biz["eligible_programs"]]
    assert "sdu-fin" in biz_ids
    assert "sdu-acc" in biz_ids
    assert "sdu-mgmt" in biz_ids
    assert "sdu-mkt" in biz_ids

    # World History + Law -> Law
    res_law = match_unt_eligibility("Всемирная история", "Основы права", 80)
    assert any(p["id"] == "sdu-law" for p in res_law["eligible_programs"])

    # Foreign Language + World History -> Translation Studies, Two Languages
    res_lang = match_unt_eligibility("Иностранный язык", "Всемирная история", 75)
    lang_ids = [p["id"] for p in res_lang["eligible_programs"]]
    assert "sdu-trans" in lang_ids
    assert "sdu-two-lang" in lang_ids


def test_us18_unt_matcher_invalid_score():
    with pytest.raises(ValueError):
        match_unt_eligibility("Математика", "Информатика", 145)

    with pytest.raises(ValueError):
        match_unt_eligibility("Математика", "Информатика", -5)


def test_us18_unt_matcher_api_endpoint():
    payload = {
        "subject_1": "Математика",
        "subject_2": "Информатика",
        "score": 118
    }
    response = client.post("/admissions/unt-matcher", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_matched"] == 3
    assert len(data["eligible_programs"]) == 3
    assert "sdu-cs" in [p["id"] for p in data["eligible_programs"]]


# ==========================================
# US19: TUITION & GRANT CALCULATOR TESTS
# ==========================================

def test_us19_tuition_calculator_base_and_discounts():
    # Computer Science with altyn_belgi (15%)
    res = calculate_tuition_and_grant(
        program_id="sdu-cs",
        unt_score=105,
        discounts=["altyn_belgi"]
    )
    assert res["program_id"] == "sdu-cs"
    assert res["base_annual_fee"] == 1850000
    assert res["base_total_fee"] == 1850000 * 4
    assert res["total_discount_percent"] == 15
    assert res["discount_amount_kzt"] == int(1850000 * 0.15)
    assert res["discounted_annual_fee"] == 1850000 - int(1850000 * 0.15)
    assert res["registration_fee_kzt"] == 60000

    sched = res["payment_schedule"]
    assert sched["semester_1"] == res["discounted_annual_fee"] // 2
    assert sched["first_payment_total"] == sched["semester_1"] + 60000


def test_us19_tuition_calculator_high_unt_and_discount_cap():
    # 125 UNT score gives 30% discount
    res = calculate_tuition_and_grant(
        program_id="sdu-cs",
        unt_score=125,
        discounts=["high_unt"]
    )
    assert res["total_discount_percent"] == 30

    # 115 UNT score gives 20% discount
    res_115 = calculate_tuition_and_grant(
        program_id="sdu-cs",
        unt_score=115,
        discounts=["high_unt"]
    )
    assert res_115["total_discount_percent"] == 20

    # Capped discount: spt_winner (30%) + high_unt 125 (30%) = 60% -> capped at 50%
    res_capped = calculate_tuition_and_grant(
        program_id="sdu-cs",
        unt_score=125,
        discounts=["spt_winner", "high_unt"]
    )
    assert res_capped["raw_discount_percent"] == 60
    assert res_capped["total_discount_percent"] == 50
    assert res_capped["is_discount_capped"] is True


def test_us19_tuition_calculator_grant_probability():
    # IT cutoff is ~115
    res_high = calculate_tuition_and_grant("sdu-cs", unt_score=118)
    assert res_high["grant_probability"]["chance"] == "high"

    res_med = calculate_tuition_and_grant("sdu-cs", unt_score=108)
    assert res_med["grant_probability"]["chance"] == "medium"

    res_low = calculate_tuition_and_grant("sdu-cs", unt_score=92)
    assert res_low["grant_probability"]["chance"] == "low"

    # Business cutoff is ~105
    res_biz_high = calculate_tuition_and_grant("sdu-fin", unt_score=106)
    assert res_biz_high["grant_probability"]["chance"] == "high"

    res_biz_med = calculate_tuition_and_grant("sdu-fin", unt_score=98)
    assert res_biz_med["grant_probability"]["chance"] == "medium"


def test_us19_tuition_calculator_api_endpoint():
    payload = {
        "program_id": "sdu-is",
        "unt_score": 112,
        "discounts": ["altyn_belgi", "high_unt"]
    }
    response = client.post("/admissions/tuition-calculator", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["program_id"] == "sdu-is"
    assert data["total_discount_percent"] == 35  # 15% + 20%
    assert data["payment_schedule"]["registration_fee"] == 60000


def test_us19_tuition_calculator_invalid_program():
    payload = {
        "program_id": "non-existent-program",
        "unt_score": 100
    }
    response = client.post("/admissions/tuition-calculator", json=payload)
    assert response.status_code == 404


# ==========================================
# CHATBOT INTEGRATION TESTS
# ==========================================

def test_chatbot_admission_guide_query():
    res = chatbot.answer_query("Какие основные этапы поступления в SDU?")
    assert res["confident"] is True
    assert res["source"] == "admission_guide"
    assert "Шаг 1" in res["answer"]
    assert "ЕНТ" in res["answer"]
    assert "admissions.sdu.edu.kz" in res["answer"]


def test_chatbot_official_links_query():
    res = chatbot.answer_query("Предоставь официальные ссылки приемной комиссии SDU")
    assert res["confident"] is True
    assert res["source"] == "official_links"
    assert "https://sdu.edu.kz" in res["answer"]
    assert "https://admissions.sdu.edu.kz" in res["answer"]
    assert "https://testcenter.kz" in res["answer"]


def test_chatbot_unt_matcher_query():
    res = chatbot.answer_query("У меня 115 баллов, предметы Математика и Информатика. Куда я могу поступить?")
    assert res["confident"] is True
    assert res["source"] == "unt_matcher"
    assert "Computer Science" in res["answer"]
    assert "Information Systems" in res["answer"]
    assert "Software Engineering" in res["answer"]


def test_chatbot_tuition_calculator_query():
    res = chatbot.answer_query("Рассчитать стоимость Computer Science со скидкой алтын белги")
    assert res["confident"] is True
    assert res["source"] == "tuition_calculator"
    assert "Computer Science" in res["answer"]
    assert "Калькулятор стоимости" in res["answer"]
    assert "60,000 KZT" in res["answer"]


def test_unified_chat_endpoint_sprint_3():
    # US7
    r_guide = client.post("/chat", json={"message": "Пошаговый гид поступления в университет"})
    assert r_guide.status_code == 200
    assert r_guide.json()["source"] == "admission_guide"

    # US9
    r_links = client.post("/chat", json={"message": "Какие официальные ссылки и сайт SDU?"})
    assert r_links.status_code == 200
    assert r_links.json()["source"] == "official_links"

    # US18
    r_unt = client.post("/chat", json={"message": "Подбор программ по ЕНТ: Математика Информатика 110 баллов"})
    assert r_unt.status_code == 200
    assert r_unt.json()["source"] == "unt_matcher"

    # US19
    r_calc = client.post("/chat", json={"message": "Рассчитать стоимость Software Engineering со скидкой алтын белги"})
    assert r_calc.status_code == 200
    assert r_calc.json()["source"] == "tuition_calculator"

