"""US7 acceptance and failure tests: synthetic policy edits never touch live data."""
import json
from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import chatbot, db_session
from app.main import app
from app.services import admission_guide as service

client = TestClient(app)
TODAY = date(2026, 10, 18)


@pytest.fixture
def policy(tmp_path, monkeypatch):
    payload = json.loads(service.PROCEDURES_FILE.read_text())
    path = tmp_path / 'procedure.json'
    path.write_text(json.dumps(payload))
    monkeypatch.setenv('ADMISSION_GUIDE_FILE', str(path))
    return path, payload


@pytest.mark.parametrize('category', ['domestic', 'international'])
@pytest.mark.parametrize('level', ['undergraduate', 'graduate'])
@pytest.mark.parametrize('lang,marker', [('ru', 'Пошаговый'), ('kk', 'қадамдық'), ('en', 'Step-by-Step')])
def test_all_twelve_routes_are_localized_and_ordered(category, level, lang, marker):
    r = client.get('/admissions/guide', params=dict(category=category, level=level, lang=lang))
    assert r.status_code == 200
    data = r.json()
    assert marker in data['title']
    assert data['language'] == lang
    assert [s['step'] for s in data['steps']] == list(range(1, data['total_steps'] + 1))
    assert all(s['source_url'].startswith('https://') for s in data['steps'])
    if level == 'graduate':
        assert 'UNT' not in data['steps'][0]['title']
        assert 'ЕНТ' not in data['steps'][0]['title']
        assert 'ҰБТ' not in data['steps'][0]['title']


@pytest.mark.parametrize('params', [
    {'category': 'nonsense'}, {'level': 'phd'}, {'lang': 'de'},
    {'category': ''}, {'level': ''}, {'lang': ''}, {'program_id': ''},
    {'program_id': 'missing'}, {'program_id': 'sdu-cs', 'level': 'graduate'},
])
def test_invalid_parameters_are_rejected(params):
    assert client.get('/admissions/guide', params=params).status_code == 422


def test_selected_program_and_verified_conditions():
    cs = client.get('/admissions/guide', params={'program_id': 'sdu-cs', 'lang': 'en'}).json()
    law = client.get('/admissions/guide', params={'program_id': 'sdu-law', 'lang': 'en'}).json()
    assert cs['program_name'] == 'Computer Science'
    assert 'Computer Science' in cs['title']
    assert 'Mathematics' in cs['program_note']
    assert cs['program_note'] != law['program_note']
    # Unverified numeric admission scores are never inferred from legacy calculators.
    assert '75 points' not in json.dumps(cs)


def test_past_deadlines_are_explicitly_closed():
    data = service.get_admission_guide(today=TODAY)
    dated = [s for s in data['steps'] if s['deadline']]
    assert {s['deadline'] for s in dated} == {'2026-07-20', '2026-08-25'}
    assert all(s['deadline_status'] == 'closed' and '2026 закрыт' in s['warning'] for s in dated)

def test_deadline_is_open_on_its_last_day_and_closed_after(policy):
    path, payload = policy
    payload['routes'][0]['steps'][1]['deadline'] = TODAY.isoformat()
    path.write_text(json.dumps(payload))
    assert service.get_admission_guide(today=TODAY)['steps'][1]['deadline_status'] == 'upcoming'
    assert service.get_admission_guide(today=date(2026, 10, 19))['steps'][1]['deadline_status'] == 'closed'


def test_stale_program_conditions_are_withheld(monkeypatch):
    stale = {'sdu-cs': {'requirements': {'domestic': {'undergraduate': {'prerequisites': {
        'status': 'published', 'source': 'https://sdu.edu.kz/en/admission-3-2/',
        'verified_on': '2026-08-01', 'review_due': '2026-08-15', 'valid_until': '2026-12-31',
        'text': {'en': 'EXPIRED PRIVATE FIXTURE'},
    }}}}}}
    monkeypatch.setattr(service, 'load_requirements', lambda: stale)
    guide = service.get_admission_guide(program_id='sdu-cs', lang='en')
    assert 'EXPIRED PRIVATE FIXTURE' not in guide['program_note']
    assert guide['program_note_source'] is None


def test_english_guide_detects_language_without_explicit_selector():
    guide = chatbot.answer_query('Admission guide for Computer Science')
    assert guide['context']['language'] == 'en'
    assert 'Step 1' in guide['answer']


def test_next_request_reads_reviewed_update_without_restart(policy):
    path, payload = policy
    old = client.get('/admissions/guide').json()
    payload['version'] = 'synthetic-revision-2'
    payload['routes'][0]['steps'][0]['text']['ru']['title'] = 'ПРОВЕРЕННОЕ ИЗМЕНЕНИЕ'
    path.write_text(json.dumps(payload))
    new = client.get('/admissions/guide').json()
    assert old['version'] != new['version']
    assert new['steps'][0]['title'] == 'ПРОВЕРЕННОЕ ИЗМЕНЕНИЕ'
    chat = client.post('/chat', json={'message': 'Пошаговый гид поступления'}).json()
    assert 'ПРОВЕРЕННОЕ ИЗМЕНЕНИЕ' in chat['answer']


@pytest.mark.parametrize('mutation', [
    {'review_due': '2026-10-17'}, {'verified_on': '2026-10-19'},
    {'status': 'draft'}, {'sources': {}}, {'routes': []},
])
def test_unreviewed_stale_and_empty_policy_is_withheld(policy, mutation):
    path, payload = policy
    payload.update(mutation)
    path.write_text(json.dumps(payload))
    r = client.get('/admissions/guide')
    assert r.status_code == 503
    assert 'steps' not in r.json()
    chat = client.post('/chat', json={'message': 'Пошаговый гид поступления'}).json()
    assert chat['confident'] is False
    assert 'Шаг 1' not in chat['answer']
    assert 'https://admissions.sdu.edu.kz' in chat['answer']


@pytest.mark.parametrize('kind', ['missing_translation', 'duplicate_step', 'foreign_source', 'malformed_json', 'missing_file'])
def test_broken_catalog_is_not_served(policy, kind):
    path, payload = policy
    if kind == 'missing_translation':
        del payload['routes'][0]['steps'][0]['text']['kk']
    elif kind == 'duplicate_step':
        payload['routes'][0]['steps'].append(deepcopy(payload['routes'][0]['steps'][0]))
    elif kind == 'foreign_source':
        payload['sources']['admission']['url'] = 'https://sdu.edu.kz.attacker.test/'
    elif kind == 'malformed_json':
        path.write_text('{')
    elif kind == 'missing_file':
        path.unlink()
    if kind not in ('malformed_json', 'missing_file'):
        path.write_text(json.dumps(payload))
    assert client.get('/admissions/guide').status_code == 503


@pytest.mark.parametrize('endpoint', ['/chat', '/chat/programs', '/chat/faq'])
@pytest.mark.parametrize('lang,question,label', [
    ('en', 'Admission guide for Computer Science undergraduate', 'Step 1'),
    ('ru', 'Пошаговый гид поступления Computer Science', 'Шаг 1'),
    ('kk', 'Computer Science қабылдау нұсқаулығы', 'Қадам 1'),
])
def test_chat_matches_api_and_preserves_program(endpoint, lang, question, label):
    r = client.post(endpoint, json={'message': question, 'language': lang})
    assert r.status_code == 200
    chat = r.json()
    assert chat['source'] == 'admission_guide'
    assert label in chat['answer']
    assert chat['context']['program_id'] == 'sdu-cs'
    assert chat['context']['study_level'] == 'undergraduate'
    api = client.get('/admissions/guide', params={'program_id': 'sdu-cs', 'lang': lang}).json()
    assert all(step['description'] in chat['answer'] for step in api['steps'])


def test_explicit_route_overrides_old_context():
    r = chatbot.answer_query('Admission guide domestic undergraduate',
        {'category': 'international', 'study_level': 'graduate'}, language='en')
    assert r['context']['category'] == 'domestic'
    assert r['context']['study_level'] == 'undergraduate'


def test_test_database_is_disposable_and_seed_is_idempotent():
    from app.models import Requirement, Program
    from scripts.migrate_to_sqlite import migrate_programs, migrate_faqs, migrate_requirements
    assert 'pm-tests-' in db_session.SQLALCHEMY_DATABASE_URL
    with db_session.SessionLocal() as db:
        before = (db.query(Requirement).count(), db.query(Program).count())
        migrate_programs(db); migrate_faqs(db); migrate_requirements(db)
        assert (db.query(Requirement).count(), db.query(Program).count()) == before
