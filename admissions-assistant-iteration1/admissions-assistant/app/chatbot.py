"""Rule-based matching engine with AI Fallback.

Implements the two Iteration 1 stories:
  - US1 Chat-Program Info: answer questions about educational programs
  - US5 Admission FAQ:      answer common admission questions

Matching approach (Idea 2 Hybrid):
1. First, we attempt normalized token-overlap scoring.
2. If confidence is >= 0.34, we return the hardcoded instant response (0 tokens used).
3. If confidence < 0.34, we trigger the AI Fallback (Gemini) to handle complex/foreign questions.
"""
import os
import re
import json
from typing import Dict, List, Optional, Tuple

from app.database import load_programs, load_faq

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
    "a", "an", "the", "is", "are", "do", "does", "what", "which", "how",
    "i", "want", "to", "for", "of", "in", "on", "about", "can", "you",
    "me", "my", "please", "tell", "much", "cost", "price", "there", "it",
    "at", "by", "from", "with", "any", "some", "have", "has", "had", "will"
}


def _tokenize(text: str) -> list:
    # Use alphanumeric regex to support program codes like 6B06101
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _score(query_tokens: list, target_tokens: list) -> float:
    if not query_tokens or not target_tokens:
        return 0.0
    
    # Use set for query to get unique search terms
    q_set = set(query_tokens)
    
    # Count how many times any query word appears in the target
    # This allows double-weighted words in target to score higher
    score = 0.0
    for q_word in q_set:
        matches = target_tokens.count(q_word)
        # Cap the bonus so one word doesn't dominate completely, but allow up to 3x weight
        score += min(matches, 3) 
        
    return score / len(q_set)


def match_program(message: str, programs: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], float]:
    """US1: find the best-matching program for a free-text question."""
    programs = programs if programs is not None else load_programs()
    q_tokens = _tokenize(message)
    best, best_score = None, 0.0
    for program in programs:
        # Double weighting for program name to prevent generic FAQs from overriding
        target = f"{program['name']} {program['name']} {program['name']} {program['code']} {program['description']} {program['degree']}"
        score = _score(q_tokens, _tokenize(target))
        if score > best_score:
            best, best_score = program, score
    return best, best_score


def match_faq(message: str, faq_entries: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], float]:
    """US5: find the best-matching FAQ entry for a free-text question."""
    faq_entries = faq_entries if faq_entries is not None else load_faq()
    q_tokens = _tokenize(message)
    best, best_score = None, 0.0
    for entry in faq_entries:
        target = " ".join(entry["keywords"]) + " " + entry["question"]
        score = _score(q_tokens, _tokenize(target))
        if score > best_score:
            best, best_score = entry, score
    return best, best_score


def answer_program_query(message: str) -> Dict:
    """Implements US1 acceptance criteria (Scenario 1 & 2)."""
    program, score = match_program(message)
    if program and score >= CONFIDENCE_THRESHOLD:
        answer = (
            f"**{program['name']}** ({program['code']}) - {program['faculty']}\n"
            f"Degree: {program['degree']}, {program['duration_years']} years\n"
            f"Cost: ~{program['approx_cost_per_year_kzt']:,} KZT/year\n"
            f"Format: {program['format']}\n"
            f"UNT Subjects: {', '.join(program.get('unt_subjects', []))}\n"
            f"Description: {program['description']}"
        )
        return {"answer": answer, "confident": True, "source": "program", "matched_id": program["id"]}
    return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}


def answer_faq_query(message: str) -> Dict:
    """Implements US5 acceptance criteria (Scenario 1 & 2)."""
    entry, score = match_faq(message)
    if entry and score >= CONFIDENCE_THRESHOLD:
        return {"answer": entry["answer"], "confident": True, "source": "faq", "matched_id": entry["id"]}
    return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}


def get_ai_fallback_response(message: str) -> Dict:
    """Uses Gemini API as a smart fallback for complex or non-English queries."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not AI_AVAILABLE or not api_key:
        print("AI Fallback skipped: Missing google-genai library or GEMINI_API_KEY")
        return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}
        
    try:
        client = genai.Client(api_key=api_key)
        programs = load_programs()
        faq = load_faq()
        
        context = (
            "You are the Smart University Admissions Assistant for SDU University in Kazakhstan. "
            "Answer user questions accurately based ONLY on the following JSON data. "
            "If the answer is not in the data, politely inform the user and suggest contacting admission@sdu.edu.kz. "
            "Keep answers concise, friendly, and well-formatted.\n\n"
            f"PROGRAMS DATA:\n{json.dumps(programs, indent=2)}\n\n"
            f"FAQ DATA:\n{json.dumps(faq, indent=2)}"
        )
        
        config = types.GenerateContentConfig(
            system_instruction=context,
            temperature=0.2,
        )
        
        # Используем актуальную модель
        chat = client.chats.create(model='gemini-3.6-flash', config=config)
        response = chat.send_message(message)
        
        return {"answer": response.text, "confident": True, "source": "ai_fallback", "matched_id": "gemini"}
    except Exception as e:
        print(f"AI Fallback Error: {e}")
        return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}


def answer_query(message: str) -> Dict:
    """Unified entry point: try both program and FAQ matching, return the stronger match."""
    program, p_score = match_program(message)
    entry, f_score = match_faq(message)

    # 1. Если токенизатор уверен - отвечаем мгновенно и бесплатно
    if p_score >= CONFIDENCE_THRESHOLD and p_score >= f_score:
        return answer_program_query(message)
    if f_score >= CONFIDENCE_THRESHOLD:
        return answer_faq_query(message)
        
    # 2. Если токенизатор не уверен (сложный вопрос/другой язык) - зовем ИИ!
    return get_ai_fallback_response(message)
