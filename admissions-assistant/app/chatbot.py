"""Rule-based matching engine with AI Fallback.

Implements the Iteration 1 stories:
  - US1 Chat-Program Info: answer questions about educational programs
  - US5 Admission FAQ:      answer common admission questions
  - US3 Requirements:       exact, provenance-gated lookup before similarity matching

Matching approach (Idea 2 Hybrid):
1. US3 (Saken's logic) gets priority if the query is strictly about requirements.
2. We attempt normalized token-overlap scoring on programs and FAQ.
3. If confidence is >= 0.34, we return the hardcoded instant response (0 tokens used).
4. For unmatched queries, Gemini selects from top matches to save tokens.
"""
import os
import re
import json
from typing import Dict, List, Optional, Tuple

from app.database import load_programs, load_faq
from app.requirements import answer_requirements

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


def _tokenize(text: str) -> list:
    # Support English, Cyrillic, and numbers for program codes
    words = re.findall(r"[a-zA-Zа-яёА-ЯЁәғқңөұүһіӘҒҚҢӨҰҮҺІ0-9]+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _score(query_tokens: list, target_tokens: list) -> float:
    if not query_tokens or not target_tokens:
        return 0.0
    
    # Use set for query to get unique search terms
    q_set = set(query_tokens)
    
    score = 0.0
    for q_word in q_set:
        matches = target_tokens.count(q_word)
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


def get_scored_faqs(message: str) -> List[Tuple[Dict, float]]:
    faq_entries = load_faq()
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


def get_ai_fallback_response(message: str, top_programs: list, top_faqs: list) -> Dict:
    """Uses Gemini API as a smart fallback with ONLY top matches to save tokens."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not AI_AVAILABLE or not api_key:
        print("AI Fallback skipped: Missing google-genai library or GEMINI_API_KEY")
        return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}
        
    try:
        client = genai.Client(api_key=api_key)
        
        # Prepare lightweight context
        programs_ctx = [{k: v for k, v in p.items() if k != "unt_subjects"} for p in top_programs]
        faq_ctx = [f for f in top_faqs if f["id"] != "faq_language"]
        
        context = (
            "You are a university admissions assistant.\n"
            "If the user is just greeting you (e.g. 'Hello', 'Привет', 'Сәлем') or making small talk, respond warmly and concisely in the same language. "
            "Return a JSON object: {\"source\": \"greeting\", \"answer\": \"Your text\"}.\n\n"
            "Otherwise, select an entry that answers the user's question. Return ONLY a JSON object "
            'with source ("program" or "faq") and matched_id, or {} if no entry answers it.\n'
            "Do not author admission conditions yourself.\n"
            f"PROGRAMS: {json.dumps(programs_ctx)}\nFAQ: {json.dumps(faq_ctx)}"
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


def answer_query(message: str, context=None, language=None) -> Dict:
    """Unified entry point (Router). Only ONE decision path."""
    
    # 1. US-3 (Saken's logic) - check strictly for requirements
    requirements = answer_requirements(message, context, language)
    if requirements is not None:
        return requirements
        
    # 2. Token Matching (US-1 & US-5)
    scored_programs = get_scored_programs(message)
    scored_faqs = get_scored_faqs(message)
    
    best_p, p_score = scored_programs[0] if scored_programs else (None, 0.0)
    best_f, f_score = scored_faqs[0] if scored_faqs else (None, 0.0)

    # 3. Fast Local Response (if confident)
    if p_score >= CONFIDENCE_THRESHOLD and p_score >= f_score:
        return _program_answer(best_p)
    if f_score >= CONFIDENCE_THRESHOLD:
        return {"answer": best_f["answer"], "confident": True, "source": "faq", "matched_id": best_f["id"]}
        
    # 4. AI Fallback (Smart prompt with top 3 only)
    top_3_programs = [p[0] for p in scored_programs[:3]]
    top_3_faqs = [f[0] for f in scored_faqs[:3]]
    
    return get_ai_fallback_response(message, top_3_programs, top_3_faqs)
