import json
from typing import List, Dict
from pathlib import Path
from .db_session import SessionLocal
from .models import Program, FAQ, Requirement

def load_programs() -> List[Dict]:
    db = SessionLocal()
    try:
        programs = db.query(Program).all()
        return [
            {
                "id": p.id,
                "code": p.code,
                "faculty": p.faculty,
                "name": p.name,
                "degree": p.degree,
                "duration_years": p.duration_years,
                "approx_cost_per_year_kzt": p.approx_cost_per_year_kzt,
                "format": p.format,
                "language": p.language,
                "unt_subjects": p.unt_subjects,
                "description": p.description
            }
            for p in programs
        ]
    finally:
        db.close()

def load_faq() -> List[Dict]:
    db = SessionLocal()
    try:
        faqs = db.query(FAQ).all()
        return [
            {
                "id": f.id,
                "question": f.question,
                "answer": f.answer,
                "keywords": f.keywords
            }
            for f in faqs
        ]
    finally:
        db.close()

def load_requirements() -> Dict:
    db = SessionLocal()
    try:
        reqs = db.query(Requirement).all()
        programs = db.query(Program).all()
        program_meta = {p.id: {"aliases": p.aliases, "codes": p.codes, "name": p.name} for p in programs}

        result = {}
        for r in reqs:
            pid = r.program_id
            if pid not in result:
                result[pid] = {
                    "name": program_meta.get(pid, {}).get("name"),
                    "aliases": program_meta.get(pid, {}).get("aliases", []),
                    "codes": program_meta.get(pid, {}).get("codes", {}),
                    "requirements": {}
                }
            
            p_req = result[pid]["requirements"]
            if r.category not in p_req:
                p_req[r.category] = {}
            if r.level not in p_req[r.category]:
                p_req[r.category][r.level] = {}
            
            topic_dict = {
                "status": r.status,
                "source": r.source,
                "checked_on": r.checked_on,
                "verified_on": r.verified_on,
                "review_due": r.review_due,
                "admission_period": r.admission_period,
                "valid_until": r.valid_until,
                "verification_note": r.verification_note,
                "text": {}
            }
            if r.text_en is not None:
                topic_dict["text"]["en"] = r.text_en
            if r.text_ru is not None:
                topic_dict["text"]["ru"] = r.text_ru
            if r.text_kk is not None:
                topic_dict["text"]["kk"] = r.text_kk
            
            topic_dict = {k: v for k, v in topic_dict.items() if v is not None}
            
            p_req[r.category][r.level][r.topic] = topic_dict
            
        return result
    finally:
        db.close()
