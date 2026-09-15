"""Rule-based matching engine for Iteration 1.

Implements the two Iteration 1 stories:
  - US1 Chat-Program Info: answer questions about educational programs
  - US5 Admission FAQ:      answer common admission questions

Matching approach: normalized token-overlap scoring against each
program's name/description and each FAQ entry's keywords/question.
This is intentionally simple (no external NLP dependency) but keeps
the "cannot confidently answer" fallback required by both stories'
acceptance criteria (Scenario 2 in each QA test).
"""
import re
from typing import Dict, List, Optional, Tuple

from app.database import load_programs, load_faq

CONFIDENCE_THRESHOLD = 0.34  # tuned low enough for short queries, see tests
FALLBACK_MESSAGE = (
    "I'm not confident I can answer that accurately. "
    "Would you like me to connect you with the admissions office "
    "(admissions@university.kz)?"
)

_STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "what", "which", "how",
    "i", "want", "to", "for", "of", "in", "on", "about", "can", "you",
    "me", "my", "please", "tell",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _score(query_tokens: set, target_tokens: set) -> float:
    if not query_tokens or not target_tokens:
        return 0.0
    overlap = query_tokens & target_tokens
    return len(overlap) / len(query_tokens)


def match_program(message: str, programs: Optional[List[Dict]] = None) -> Tuple[Optional[Dict], float]:
    """US1: find the best-matching program for a free-text question."""
    programs = programs if programs is not None else load_programs()
    q_tokens = _tokenize(message)
    best, best_score = None, 0.0
    for program in programs:
        target = f"{program['name']} {program['description']} {program['degree']}"
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
            f"{program['name']} ({program['degree']}, {program['duration_years']} years): "
            f"{program['description']} Cost: ~{program['cost_per_year_kzt']:,} KZT/year. "
            f"Format: {program['format']}."
        )
        return {"answer": answer, "confident": True, "source": "program", "matched_id": program["id"]}
    return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}


def answer_faq_query(message: str) -> Dict:
    """Implements US5 acceptance criteria (Scenario 1 & 2)."""
    entry, score = match_faq(message)
    if entry and score >= CONFIDENCE_THRESHOLD:
        return {"answer": entry["answer"], "confident": True, "source": "faq", "matched_id": entry["id"]}
    return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}


def answer_query(message: str) -> Dict:
    """Unified entry point: try both program and FAQ matching, return the stronger match."""
    program, p_score = match_program(message)
    entry, f_score = match_faq(message)

    if p_score >= CONFIDENCE_THRESHOLD and p_score >= f_score:
        return answer_program_query(message)
    if f_score >= CONFIDENCE_THRESHOLD:
        return answer_faq_query(message)
    return {"answer": FALLBACK_MESSAGE, "confident": False, "source": None, "matched_id": None}
