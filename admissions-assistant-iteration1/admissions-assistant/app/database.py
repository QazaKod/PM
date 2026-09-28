"""Simple JSON-backed data access layer.

For Iteration 1 the "knowledge base" lives in data/*.json to keep the
project runnable without a real DB server. Swapping this for PostgreSQL
later only means rewriting these two loader functions.
"""
import json
from pathlib import Path
from typing import List, Dict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_programs() -> List[Dict]:
    with open(DATA_DIR / "programs.json", encoding="utf-8") as f:
        return json.load(f)


def load_faq() -> List[Dict]:
    with open(DATA_DIR / "faq.json", encoding="utf-8") as f:
        return json.load(f)


def load_requirements() -> Dict:
    """US3: exact program -> category -> level -> topic, with provenance."""
    with open(DATA_DIR / "requirements.json", encoding="utf-8") as f:
        return json.load(f)
