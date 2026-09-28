"""No test may call a paid or network-backed AI service."""
import pytest
from app import chatbot


@pytest.fixture(autouse=True)
def offline_ai(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(chatbot, 'AI_AVAILABLE', False)
