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
    result = chatbot.answer_query("How much does the Computer Science program cost?")
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
        result = chatbot.answer_query(question)
        assert result["confident"] is True, f"Expected confident answer for: {question}"
        assert result["matched_id"] == expected_id, f"Wrong program matched for: {question}"


def test_us1_scenario2_chatbot_cannot_answer_confidently():
    result = chatbot.answer_query("What's the weather like on Mars today?")
    assert result["confident"] is False
    assert result["source"] is None
    assert "connect you with the admissions office" in result["answer"]


# --- US5: Admission FAQ ------------------------------------------------------

def test_us5_scenario1_successful_faq_query():
    result = chatbot.answer_query("What documents are required for admission?")
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
        result = chatbot.answer_query(question)
        assert result["confident"] is True, f"Expected confident answer for: {question}"
        assert result["matched_id"] == expected_id, f"Wrong FAQ matched for: {question}"


def test_us5_scenario2_question_not_covered_in_faq():
    result = chatbot.answer_query("Can I bring my dog to campus?")
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


# --- Revamped AI Assistant & Fallback Behavior --------------------------------

def test_ai_answers_when_keywords_do_not_match_via_rest(monkeypatch):
    """When keyword matchers miss and AI is active (via httpx REST), AI answers confidently."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(chatbot, "AI_AVAILABLE", True)
    monkeypatch.setattr(chatbot, "genai", None)
    monkeypatch.setattr(chatbot, "HTTPX_AVAILABLE", True)

    captured = {}

    def fake_rest_call(api_key, system_instruction, message):
        captured["api_key"] = api_key
        captured["system_instruction"] = system_instruction
        captured["message"] = message
        return '{"source": "ai", "confident": true, "answer": "Кампус SDU в Каскелене включает учебные корпуса, технопарк, библиотеку и 4 блока общежития."}'

    monkeypatch.setattr(chatbot, "_call_gemini_rest", fake_rest_call)

    result = chatbot.answer_query("Расскажи про кампус SDU, студенческую жизнь и какие есть клубы?")
    assert result["confident"] is True
    assert result["source"] == "ai"
    assert result["matched_id"] == "ai_assistant"
    assert "SDU" in result["answer"]
    assert "SDU_KNOWLEDGE_BASE" in captured["system_instruction"]


def test_ai_returns_fallback_only_when_even_ai_is_unconfident(monkeypatch):
    """Fallback message is returned ONLY in extreme cases when even the AI reports unconfident."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(chatbot, "AI_AVAILABLE", True)
    monkeypatch.setattr(chatbot, "genai", None)
    monkeypatch.setattr(chatbot, "HTTPX_AVAILABLE", True)

    monkeypatch.setattr(
        chatbot,
        "_call_gemini_rest",
        lambda api_key, sys_inst, msg: '{"source": "unconfident", "confident": false}',
    )

    result = chatbot.answer_query("Как приготовить бешбармак на Марсе?")
    assert result["confident"] is False
    assert result["source"] is None
    assert result["matched_id"] is None
    assert result["answer"] == chatbot.FALLBACK_MESSAGE


def test_comparative_query_prefers_ai_when_ai_is_active(monkeypatch):
    """Comparative/open-ended questions route to AI instead of dumping a single static program card."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(chatbot, "AI_AVAILABLE", True)
    monkeypatch.setattr(chatbot, "genai", None)
    monkeypatch.setattr(chatbot, "HTTPX_AVAILABLE", True)

    monkeypatch.setattr(
        chatbot,
        "_call_gemini_rest",
        lambda api_key, sys_inst, msg: (
            '{"source": "ai", "confident": true, '
            '"answer": "Computer Science фокусируется на алгоритмах и ИИ, а Software Engineering — на промышленной разработке ПО."}'
        ),
    )

    result = chatbot.answer_query("Чем отличается Computer Science от Software Engineering?")
    assert result["confident"] is True
    assert result["source"] == "ai"
    assert "Computer Science" in result["answer"]
    assert "Software Engineering" in result["answer"]


def test_gemini_rest_model_fallback_on_http_error(monkeypatch):
    """_call_gemini_rest falls back to the next Gemini model if the primary returns non-200."""
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, params=None, json=None, timeout=None):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(503, {"error": "overloaded"})
        return FakeResponse(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": '{"source": "ai", "confident": true, "answer": "OK response"}'}]}}
                ]
            },
        )

    monkeypatch.setattr(chatbot.httpx, "post", fake_post)
    raw = chatbot._call_gemini_rest("fake-key", "sys", "hello")
    assert len(calls) == 2
    assert '"answer": "OK response"' in raw


def test_shorthand_unt_subject_query_without_score():
    """Queries like 'какие программы есть по инфо мат ?' match UNT programs without needing AI."""
    result = chatbot.answer_query("какие программы есть по инфо мат ?")
    assert result["confident"] is True
    assert result["source"] == "unt_matcher"
    assert "Computer Science" in result["answer"]
    assert "Information Systems" in result["answer"]


def test_operator_contact_query_matches_official_links():
    """Queries asking to connect with an operator ('соеденить с оператором') return official contacts."""
    result = chatbot.answer_query("соеденить с оператором")
    assert result["confident"] is True
    assert result["source"] == "official_links"
    assert "admission@sdu.edu.kz" in result["answer"]


def test_russian_program_aliases_match_program_and_tuition_calculator():
    """Russian/Kazakh program aliases from DB match accurately in both program lookup and tuition calculator."""
    calc_res = chatbot.answer_query("Рассчитать стоимость Финансы со скидкой алтын белги")
    assert calc_res["source"] == "tuition_calculator"
    assert calc_res["matched_id"] == "sdu-fin"

    prog_res = chatbot.answer_query("Сколько стоит программа Финансы?")
    assert prog_res["confident"] is True
    assert prog_res["source"] == "program"
    assert prog_res["matched_id"] == "sdu-fin"


def test_non_unt_program_questions_do_not_trigger_unt_matcher(monkeypatch):
    """General faculty/exchange/degree program questions must not be hijacked by _handle_unt_matcher."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(chatbot, "AI_AVAILABLE", True)
    monkeypatch.setattr(chatbot, "genai", None)
    monkeypatch.setattr(chatbot, "HTTPX_AVAILABLE", True)
    monkeypatch.setattr(
        chatbot,
        "_call_gemini_rest",
        lambda api_key, sys_inst, msg: '{"source": "ai", "confident": true, "answer": "На факультете бизнеса есть Финансы, Менеджмент, Маркетинг и Учет и аудит."}',
    )

    for query in (
        "Какие программы есть на факультете бизнеса?",
        "Какие программы есть для магистратуры?",
        "Какие программы есть по обмену?",
        "Что лучше: CS или Иняз, какие программы выбрать?",
    ):
        res = chatbot.answer_query(query)
        assert res["source"] == "ai", f"Expected AI source for '{query}', got {res['source']}"
        assert res["confident"] is True


def test_multi_turn_us3_context_does_not_trap_subsequent_ai_or_faq_queries(monkeypatch):
    """Switching topics after a pending or completed US3 query exits US3 and routes to FAQ, program, or AI."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(chatbot, "AI_AVAILABLE", True)
    monkeypatch.setattr(chatbot, "genai", None)
    monkeypatch.setattr(chatbot, "HTTPX_AVAILABLE", True)
    monkeypatch.setattr(
        chatbot,
        "_call_gemini_rest",
        lambda api_key, sys_inst, msg: '{"source": "ai", "confident": true, "answer": "AI comparison response"}',
    )

    # Turn 1: enters US3 pending category clarification
    r1 = chatbot.answer_query("Какие требования для Computer Science?")
    assert r1["source"] == "requirements"
    assert r1["context"]["pending"] == "category"

    # Turn 2a: user switches to comparative AI question while pending='category'
    r2_ai = chatbot.answer_query("Чем отличается Computer Science от Software Engineering?", context=r1["context"])
    assert r2_ai["source"] == "ai"
    assert r2_ai["confident"] is True

    # Turn 2b: user switches to FAQ question while pending='category'
    r2_faq = chatbot.answer_query("What is the SPT Olympiad?", context=r1["context"])
    assert r2_faq["source"] == "faq"
    assert r2_faq["matched_id"] == "faq_spt"

    # Turn 2c: logged-in profile context (pending=None) does not hijack general program inquiry
    r2_prog = chatbot.answer_query(
        "Tell me about the Software Engineering program",
        context={"category": "domestic", "study_level": "undergraduate"},
    )
    assert r2_prog["source"] == "program"
    assert r2_prog["matched_id"] == "sdu-se"


def test_nuanced_single_program_questions_route_to_ai_when_active(monkeypatch):
    """Advisory, difficulty, curriculum, transfer, or military training questions route to AI instead of static card."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(chatbot, "AI_AVAILABLE", True)
    monkeypatch.setattr(chatbot, "genai", None)
    monkeypatch.setattr(chatbot, "HTTPX_AVAILABLE", True)
    monkeypatch.setattr(
        chatbot,
        "_call_gemini_rest",
        lambda api_key, sys_inst, msg: '{"source": "ai", "confident": true, "answer": "Подробный ответ ИИ про обучение на программе."}',
    )

    for query in (
        "Сложно ли учиться на Computer Science в СДУ?",
        "Какие языки программирования учат на Software Engineering?",
        "Можно ли перевестись на Computer Science из другого университета?",
        "Есть ли военная кафедра в СДУ для студентов Computer Science?",
        "На каком языке проходит обучение в СДУ?",
    ):
        res = chatbot.answer_query(query)
        assert res["source"] == "ai", f"Expected AI source for '{query}', got {res['source']}"
        assert res["confident"] is True


def test_chat_endpoint_accepts_client_history_for_multi_turn_memory():
    """POST /chat uses client-supplied history turns for guest sessions."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/chat",
        json={
            "message": "А сколько стоит обучение туда?",
            "history": [
                {"sender": "user", "message": "Tell me about the Finance program"},
                {"sender": "bot", "message": "**Finance** (6B04104) - SDU Business School"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confident"] is True
    assert data["source"] == "program"
    assert data["matched_id"] == "sdu-fin"

