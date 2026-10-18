"""Regression checks found during the final Sprint 3 review."""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import chatbot
from app.db_session import SessionLocal
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.mark.parametrize('name', ['International Law', 'International Relations'])
@pytest.mark.parametrize('category', ['domestic', 'international'])
def test_program_name_does_not_override_applicant_category(name, category):
    result = chatbot.answer_query(f'Admission guide for {name} {category} undergraduate', language='en')
    assert result['confident'] is True
    assert result['context']['category'] == category


def test_ambiguous_program_does_not_reuse_previous_program():
    result = chatbot.answer_query('Admission guide for Computer Science and Finance',
        {'program_id': 'sdu-law', 'category': 'domestic'}, language='en')
    assert result['confident'] is False
    assert 'select one program' in result['answer']
    assert 'Jurisprudence' not in result['answer']


def test_authenticated_admin_views_and_configured_logs():
    with SessionLocal() as db:
        db.add(User(email='review-admin@example.test', full_name='Review Admin',
            hashed_password=hash_password('ReviewOnly123!'), role='admin', is_active=True, is_verified=True))
        db.commit()
    log_path = Path(os.environ['LOG_FILE'])
    with log_path.open('a') as log:
        log.write('SPRINT3-ISOLATED-LOG-CHECK\n')
    with TestClient(app) as client:
        login = client.post('/admin/login', data={'username':'review-admin@example.test', 'password':'ReviewOnly123!'})
        assert login.status_code == 200
        assert client.get('/admin/program/list').status_code == 200
        logs = client.get('/admin/logs')
        assert logs.status_code == 200
        assert 'SPRINT3-ISOLATED-LOG-CHECK' in logs.text
