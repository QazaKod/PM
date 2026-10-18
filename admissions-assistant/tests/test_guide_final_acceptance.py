"""Regressions found by the independent final acceptance audit."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.admission_guide import PROCEDURES_FILE

client = TestClient(app)


@pytest.mark.parametrize('field', ['title', 'description'])
def test_whitespace_only_translation_is_withheld(tmp_path, monkeypatch, field):
    data = json.loads(PROCEDURES_FILE.read_text())
    data['routes'][0]['steps'][0]['text']['en'][field] = ' \t\n '
    path = tmp_path / 'blank.json'
    path.write_text(json.dumps(data))
    monkeypatch.setenv('ADMISSION_GUIDE_FILE', str(path))
    assert client.get('/admissions/guide', params={'lang':'en'}).status_code == 503
    chat = client.post('/chat', json={'message':'Admission guide', 'language':'en'}).json()
    assert chat['confident'] is False


@pytest.mark.parametrize('program_id,step_id', [
    ('sdu-two-lang', 'pedagogical-exam'), ('sdu-journalism', 'creative-exam'),
])
def test_program_specific_entrance_action_precedes_grant_application(program_id, step_id):
    guide = client.get('/admissions/guide', params={'program_id':program_id,'lang':'en'}).json()
    ids = [step['id'] for step in guide['steps']]
    assert ids.index(step_id) < ids.index('funding')
    assert [s['step'] for s in guide['steps']] == list(range(1,len(ids)+1))
    # These instructions must not spill into an unrelated program or category.
    cs = client.get('/admissions/guide', params={'program_id':'sdu-cs'}).json()
    foreign = client.get('/admissions/guide', params={'program_id':program_id,'category':'international'}).json()
    assert step_id not in [s['id'] for s in cs['steps']]
    assert step_id not in [s['id'] for s in foreign['steps']]


@pytest.mark.parametrize('level', ['undergraduate','graduate'])
def test_international_language_assessment_precedes_interview(level):
    guide = client.get('/admissions/guide', params={'category':'international','level':level,'lang':'en'}).json()
    ids = [step['id'] for step in guide['steps']]
    assert ids.index('language') < ids.index('selection') < ids.index('enrollment')


def test_international_deadlines_have_intake_scope_and_are_not_applied_to_master():
    bachelor = client.get('/admissions/guide', params={'category':'international','lang':'en'}).json()
    application = next(s for s in bachelor['steps'] if s['id']=='application')
    assert application['deadline'] == '2026-11-30'
    assert application['deadline_status'] == 'upcoming'
    assert 'spring' in application['description'] and 'fall' in application['description']
    master = client.get('/admissions/guide', params={'category':'international','level':'graduate'}).json()
    assert all(s['deadline'] is None for s in master['steps'])


@pytest.mark.parametrize('failure', ['source', 'translation'])
def test_program_specific_action_requires_reviewed_source_and_full_translation(tmp_path,monkeypatch,failure):
    data=json.loads(PROCEDURES_FILE.read_text())
    step=data['routes'][0]['program_steps']['sdu-two-lang'][0]
    if failure=='source': step['source_id']='missing'
    else: del step['text']['kk']
    path=tmp_path/'invalid-extra.json';path.write_text(json.dumps(data))
    monkeypatch.setenv('ADMISSION_GUIDE_FILE',str(path))
    assert client.get('/admissions/guide').status_code == 503


@pytest.mark.parametrize('verified,due', [('2026-10-01','2026-10-17'),('2026-10-19','2026-11-01')])
def test_freshness_gate_rejects_well_formed_out_of_window_publications(tmp_path,monkeypatch,verified,due):
    data=json.loads(PROCEDURES_FILE.read_text())
    data.update(verified_on=verified,review_due=due)
    path=tmp_path/'outside-window.json';path.write_text(json.dumps(data))
    monkeypatch.setenv('ADMISSION_GUIDE_FILE',str(path))
    response=client.get('/admissions/guide')
    assert response.status_code == 503
    # Verify the freshness gate, not just an invalid date-interval schema.
    assert 'review has expired or is future-dated' in response.json()['detail']
