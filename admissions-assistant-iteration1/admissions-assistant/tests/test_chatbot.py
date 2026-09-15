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
    assert result["matched_id"] == "cs-bachelor"
    assert "Computer Science" in result["answer"]


def test_us1_scenario1_five_different_program_questions_pass():
    """System: (Pass) Five different program-related questions are answered correctly."""
    questions_and_expected_ids = [
        ("Tell me about the Information Technology bachelor program", "it-bachelor"),
        ("What is the duration of Business Administration?", "ba-bachelor"),
        ("Is there a Data Science master program?", "ds-master"),
        ("What format is Computer Science offered in?", "cs-bachelor"),
        ("How much is tuition for Information Technology?", "it-bachelor"),
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
    result = chatbot.answer_faq_query("What is the application deadline?")
    assert result["confident"] is True
    assert result["source"] == "faq"
    assert result["matched_id"] == "faq-1"


def test_us5_scenario1_five_different_faq_questions_pass():
    """System: (Pass) Five different FAQ questions are answered correctly."""
    questions_and_expected_ids = [
        ("When do I need to apply by?", "faq-1"),
        ("What documents do I need to submit?", "faq-2"),
        ("How much is the tuition price?", "faq-3"),
        ("Is there a scholarship available?", "faq-4"),
        ("How can I contact the admissions office?", "faq-5"),
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
    result = chatbot.answer_query("Tell me about the Data Science master program")
    assert result["source"] == "program"


def test_unified_chat_routes_to_faq_when_stronger_match():
    result = chatbot.answer_query("What documents are required to apply?")
    assert result["source"] == "faq"
