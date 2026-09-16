"""
Maps directly to the QA Test entries in the User Story Schedule:

US1QATest (Story 1 — Chat-Program Info)
  Scenario 1: Successful program query -> correct info returned
  Scenario 2: Chatbot cannot answer confidently -> fallback + staff offer

US5QATest (Story 5 — Admission FAQ)
  Scenario 1: Successful FAQ query -> correct FAQ answer
  Scenario 2: Question not covered in FAQ -> fallback + staff offer
"""
from app import chatbot

# --- US1: Chat-Program Info -------------------------------------------------

def test_us1_scenario1_successful_program_query():
    result = chatbot.answer_program_query("How much does the Computer Science program cost?")
    assert result["confident"] is True
    assert result["source"] == "program"
    assert result["matched_id"] == "sdu-cs"
    assert "Computer Science" in result["answer"]


def test_us1_scenario1_five_different_program_questions_pass():
    """System: (Pass) Five different program-related questions are answered correctly."""
    questions_and_expected_ids = [
        ("Tell me about the Information Systems bachelor program", "sdu-is"),
        ("Tell me about the Management program", "sdu-mgmt"),
        ("Is there a Mathematical Modeling program?", "sdu-mcm"),
        ("What format is Computer Science offered in?", "sdu-cs"),
        ("How much is tuition for Software Engineering?", "sdu-se"),
    ]
    for question, expected_id in questions_and_expected_ids:
        result = chatbot.answer_program_query(question)
        assert result["confident"] is True, f"Expected confident answer for: {question}"
        assert result["matched_id"] == expected_id, f"Wrong program matched for: {question}"


def test_us1_scenario2_chatbot_cannot_answer_confidently():
    result = chatbot.answer_program_query("What's the weather like on Mars today?")
    assert result["confident"] is False
    assert result["source"] is None
    assert "connect you with the admissions office" in result["answer"]


# --- US5: Admission FAQ ------------------------------------------------------

def test_us5_scenario1_successful_faq_query():
    result = chatbot.answer_faq_query("What documents are required for admission?")
    assert result["confident"] is True
    assert result["source"] == "faq"
    assert result["matched_id"] == "faq_documents"


def test_us5_scenario1_five_different_faq_questions_pass():
    """System: (Pass) Five different FAQ questions are answered correctly."""
    questions_and_expected_ids = [
        ("What is the SPT Olympiad?", "faq_spt"),
        ("What documents do I need for admission?", "faq_documents"),
        ("How are tuition fees paid?", "faq_payment"),
        ("Is there a student dorm or accommodation?", "faq_dorm"),
        ("Can I study with a state grant?", "faq_ministry"),
    ]
    for question, expected_id in questions_and_expected_ids:
        result = chatbot.answer_faq_query(question)
        assert result["confident"] is True, f"Expected confident answer for: {question}"
        assert result["matched_id"] == expected_id, f"Wrong FAQ matched for: {question}"


def test_us5_scenario2_question_not_covered_in_faq():
    result = chatbot.answer_faq_query("Can I bring my dog to campus?")
    assert result["confident"] is False
    assert result["source"] is None
    assert "connect you with the admissions office" in result["answer"]


# --- Unified /chat routing ----------------------------------------------------

def test_unified_chat_routes_to_program_when_stronger_match():
    result = chatbot.answer_query("Tell me about the Software Engineering program")
    assert result["source"] == "program"


def test_unified_chat_routes_to_faq_when_stronger_match():
    result = chatbot.answer_query("What documents are required to apply?")
    assert result["source"] == "faq"
