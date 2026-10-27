"""All tests use a disposable seeded DB and stub outbound messaging."""
import os
import tempfile
from pathlib import Path
from datetime import date

# Set before any app module is imported (including test collection).
_sandbox = tempfile.TemporaryDirectory(prefix="pm-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_sandbox.name) / 'tests.db'}"
os.environ["TESTING"] = "1"
os.environ["GEMINI_API_KEY"] = ""
os.environ["LOG_FILE"] = str(Path(_sandbox.name) / 'tests.log')

import pytest
from app import chatbot
from app.db_session import init_db, SessionLocal
from scripts.migrate_to_sqlite import migrate_programs, migrate_faqs, migrate_requirements


@pytest.fixture(scope="session", autouse=True)
def isolated_database():
    init_db()
    with SessionLocal() as db:
        migrate_programs(db)
        migrate_faqs(db)
        migrate_requirements(db)
    yield
    from app.db_session import engine
    engine.dispose()


@pytest.fixture(autouse=True)
def offline_messaging(monkeypatch):
    from app.routers import auth
    from app import telegram_service
    monkeypatch.setattr(auth, 'is_smtp_configured', lambda: False)
    monkeypatch.setattr(auth, 'is_telegram_configured', lambda: False)
    for name in ('send_account_verification_email', 'send_password_reset_email', 'send_sms_verification_code', 'send_telegram_reset_code', 'send_telegram_verification_code'):
        monkeypatch.setattr(auth, name, lambda *args, **kwargs: False)
    monkeypatch.setattr(telegram_service, 'send_telegram_message', lambda *args, **kwargs: False)


@pytest.fixture(autouse=True)
def offline_ai(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(chatbot, 'AI_AVAILABLE', False)


@pytest.fixture(autouse=True)
def fixed_guide_review_date(monkeypatch):
    # Functional tests use the checked-in policy's review date. Explicit stale
    # and future-date tests still exercise the production expiry checks.
    from app.services import admission_guide
    monkeypatch.setattr(admission_guide, 'local_today', lambda: date(2026, 10, 18))
