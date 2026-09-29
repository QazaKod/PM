import json
import os
import sys
from pathlib import Path

# Add the project root to sys.path so we can import 'app'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from app.db_session import SessionLocal, init_db
from app.models import Program, FAQ, Requirement

DATA_DIR = PROJECT_ROOT / "data"

def migrate_programs(db):
    print("Migrating programs...")
    with open(DATA_DIR / "programs.json", encoding="utf-8") as f:
        programs = json.load(f)
    
    # We will temporarily load requirements.json just to extract aliases/codes 
    # to store them in the Program table directly, as requested by our unified model.
    with open(DATA_DIR / "requirements.json", encoding="utf-8") as f:
        req_data = json.load(f)

    for p in programs:
        pid = p["id"]
        # Extract US-3 specific info if it exists
        aliases = req_data.get(pid, {}).get("aliases", [])
        codes = req_data.get(pid, {}).get("codes", {})

        program = Program(
            id=pid,
            code=p.get("code"),
            faculty=p.get("faculty"),
            name=p.get("name"),
            degree=p.get("degree"),
            duration_years=p.get("duration_years"),
            approx_cost_per_year_kzt=p.get("approx_cost_per_year_kzt"),
            format=p.get("format"),
            language=p.get("language", []),
            unt_subjects=p.get("unt_subjects", []),
            description=p.get("description"),
            aliases=aliases,
            codes=codes
        )
        db.merge(program) # merge handles insert/update
    db.commit()


def migrate_faqs(db):
    print("Migrating FAQs...")
    with open(DATA_DIR / "faq.json", encoding="utf-8") as f:
        faqs = json.load(f)
    
    for faq in faqs:
        f = FAQ(
            id=faq["id"],
            question=faq.get("question"),
            answer=faq.get("answer"),
            keywords=faq.get("keywords", [])
        )
        db.merge(f)
    db.commit()


def migrate_requirements(db):
    print("Migrating requirements (flattening)...")
    with open(DATA_DIR / "requirements.json", encoding="utf-8") as f:
        req_data = json.load(f)
    
    for pid, pdata in req_data.items():
        reqs = pdata.get("requirements", {})
        
        for category, cat_data in reqs.items():
            for level, level_data in cat_data.items():
                for topic, topic_data in level_data.items():
                    # Flatten out text fields
                    text_dict = topic_data.get("text", {})
                    
                    r = Requirement(
                        program_id=pid,
                        category=category,
                        level=level,
                        topic=topic,
                        status=topic_data.get("status"),
                        source=topic_data.get("source"),
                        checked_on=topic_data.get("checked_on"),
                        verified_on=topic_data.get("verified_on"),
                        review_due=topic_data.get("review_due"),
                        admission_period=topic_data.get("admission_period"),
                        valid_until=topic_data.get("valid_until"),
                        verification_note=topic_data.get("verification_note"),
                        text_en=text_dict.get("en"),
                        text_ru=text_dict.get("ru"),
                        text_kk=text_dict.get("kk")
                    )
                    db.add(r)
    db.commit()

def main():
    print("Initializing Database...")
    init_db()
    db = SessionLocal()
    try:
        migrate_programs(db)
        migrate_faqs(db)
        migrate_requirements(db)
        print("Migration complete! Database is populated.")
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
