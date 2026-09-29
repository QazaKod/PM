"""US3 acceptance tests. All numeric admission fixtures here are SYNTHETIC.

They test publication/routing behavior, never supply production admission data.
"""
from copy import deepcopy
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import chatbot
from app.database import load_requirements
from app.main import app
from app.requirements import answer_requirements

TODAY = date(2026, 9, 28)
client = TestClient(app)


@pytest.fixture
def data():
    data = deepcopy(load_requirements())
    for p in data.values():
        for category, levels in p['requirements'].items():
            for level, fields in levels.items():
                for topic in fields:
                    fields[topic] = {
                        'status': 'published', 'source': 'https://sdu.edu.kz/test-fixture/',
                        'verified_on': '2026-09-28', 'checked_on': '2026-09-28',
                        'review_due': '2026-10-28', 'valid_until': '2026-12-31', 'admission_period': '2026–2027',
                        'text': {lang: f'SYNTHETIC {p["name"]} {category} {level} {topic} {lang}: 123' for lang in ('en','ru','kk')},
                    }
    return data


def ask(message, data, context=None, **kwargs):
    return answer_requirements(message, context, data=data, today=TODAY, **kwargs)


@pytest.mark.parametrize('question,pid,category,level,topic,lang', [
    ('What UNT score is required for Computer Science domestic undergraduate?', 'sdu-cs','domestic','undergraduate','exams','en'),
    ('Какие предметы нужны для Финансы, Казахстан, бакалавриат?', 'sdu-fin','domestic','undergraduate','prerequisites','ru'),
    ('Ақпараттық жүйелер бакалавриат шетелдік талапкер үшін тіл талаптары қандай?', 'sdu-is','international','undergraduate','language','kk'),
    ('What qualifications for Management international graduate?', 'sdu-mgmt','international','graduate','prerequisites','en'),
    ('Какой IELTS для Software Engineering, иностранный абитуриент, магистратура?', 'sdu-se','international','graduate','language','ru'),
    ('What subjects for International Law domestic undergraduate?', 'sdu-ilaw','domestic','undergraduate','prerequisites','en'),
])
def test_distinct_requirements(question,pid,category,level,topic,lang,data):
    result = ask(question,data)
    assert result['matched_id'] == pid
    assert result['confident']
    assert f'{category} {level} {topic} {lang}: 123' in result['answer']
    assert result['context']['language'] == lang


@pytest.mark.parametrize('first,program,category,level,lang', [
    ('What IELTS score do I need?','Computer Science','domestic','undergraduate','en'),
    ('Какой IELTS нужен?','Computer Science','иностранный','бакалавриат','ru'),
    ('Қандай пәндер керек?','Finance','отандық','бакалавриат','kk'),
])
def test_clarification_continues_original_topic(first,program,category,level,lang,data):
    r = ask(first,data)
    assert r['context']['pending'] == 'program_id'
    original_topics = r['context']['topics']
    for reply, expected_pending in [(program,'category'),(category,'study_level'),(level,None)]:
        r = ask(reply,data,r['context'])
        assert r['context']['pending'] == expected_pending
    assert r['context']['language'] == lang
    assert r['context']['topics'] == original_topics
    assert r['confident']


@pytest.mark.parametrize('status', ['under_review','unverified','missing','draft'])
def test_unapproved_values_never_leak(status,data):
    data['sdu-cs']['requirements']['domestic']['undergraduate']['exams']['status'] = status
    r = ask('UNT score Computer Science domestic undergraduate',data)
    assert not r['confident']
    assert '123' not in r['answer']
    if status == 'under_review':
        assert 'No subscription has been created' in r['answer']
        assert r['notification_available'] is False
        followup = ask('Notify me',data,r['context'])
        assert 'No subscription' in followup['answer']


@pytest.mark.parametrize('change', [
    {'review_due':'2026-09-27'}, {'verified_on':'2027-01-01'},
    {'valid_until':'2026-09-01'}, {'verified_on':'2025-09-28','review_due':'2027-01-01'},
    {'verified_on':None}, {'review_due':'invalid'},
    {'source':'https://sdu.edu.kz.attacker.test/'}, {'text':{}},
])
def test_stale_or_invalid_provenance_withholds_values(change,data):
    data['sdu-cs']['requirements']['domestic']['undergraduate']['exams'].update(change)
    r = ask('UNT score Computer Science domestic undergraduate',data)
    assert not r['confident']
    assert '123' not in r['answer']


def test_outdated_status(data):
    data['sdu-cs']['requirements']['domestic']['undergraduate']['exams']['verified_on']='2026-08-28'
    data['sdu-cs']['requirements']['domestic']['undergraduate']['exams']['review_due']='2026-09-27'
    assert ask('UNT score Computer Science domestic undergraduate',data)['requirement_status']=='outdated'


def test_missing_program_record_does_not_borrow_other_category(data):
    del data['sdu-cs']['requirements']['international']['graduate']
    r=ask('IELTS Computer Science international graduate',data)
    assert r['requirement_status']=='missing'
    assert '123' not in r['answer']


def test_unknown_program_no_approximate_match(data):
    r=ask('What requirements for Medicine domestic undergraduate?',data)
    assert r['requirement_status']=='clarification'
    assert r['matched_id'] is None
    assert '123' not in r['answer']
    r=ask('Astrophysics',data,r['context'])
    assert r['context']['pending']=='program_id'


def test_new_unknown_program_does_not_reuse_previous(data):
    r=ask('IELTS Computer Science domestic undergraduate',data)
    r=ask('What IELTS for Medicine?',data,r['context'])
    assert r['context']['pending']=='program_id'
    assert '123' not in r['answer']


def test_multiple_programs_and_categories_ask_again(data):
    r=ask('Requirements Computer Science or Finance domestic undergraduate',data)
    assert r['context']['pending']=='program_id'
    r=ask('Requirements Finance domestic or international undergraduate',data)
    assert r['context']['pending']=='category'


def test_exact_official_code_and_level(data):
    r=ask('IELTS 6B06102 domestic',data)
    assert r['matched_id']=='sdu-cs'
    assert r['context']['study_level']=='undergraduate'
    r=ask('IELTS 7M06101 domestic',data)
    assert r['matched_id']=='sdu-is'
    assert r['context']['study_level']=='graduate'


def test_future_admission_period_withheld(data):
    r=ask('2027 requirements Computer Science domestic undergraduate',data)
    assert r['requirement_status']=='unverified'
    assert '123' not in r['answer']


def test_unrelated_query_leaves_requirement_flow(data):
    assert ask('What is the tuition cost?',data,{'language':'en','pending':None}) is None


@pytest.mark.parametrize('endpoint',['/chat','/chat/programs','/chat/faq'])
def test_api_uses_us3_on_all_chat_endpoints(endpoint,monkeypatch):
    ai=Mock(side_effect=AssertionError('US3 must not call AI'))
    monkeypatch.setattr(chatbot,'get_ai_fallback_response',ai)
    r=client.post(endpoint,json={'message':'Какие требования для Computer Science?'})
    assert r.status_code==200
    d=r.json()
    assert d['source']=='requirements'
    assert d['context']['pending']=='category'
    r=client.post(endpoint,json={'message':'domestic undergraduate','context':d['context']})
    assert r.status_code==200
    assert r.json()['context']['pending'] is None
    assert r.json()['context']['language']=='ru'
    ai.assert_not_called()


def test_api_context_validation_and_isolation():
    assert client.post('/chat',json={'message':'IELTS','context':{'category':'anything'}}).status_code==422
    assert client.post('/chat',json={'message':'IELTS','language':'fr'}).status_code==422
    client.post('/chat',json={'message':'IELTS Computer Science domestic undergraduate'})
    assert client.post('/chat',json={'message':'IELTS'}).json()['context']['pending']=='program_id'


@pytest.mark.parametrize('question,source',[
    ('How much does Computer Science cost?','program'),
    ('Tell me about Software Engineering','program'),
    ('What documents are required to apply?','faq'),
    ('Is there a student dorm?','faq'),
    ('What is the SPT Olympiad?','faq'),
])
def test_unified_regressions(question,source):
    assert client.post('/chat',json={'message':question}).json()['source']==source


def test_real_data_contains_no_synthetic_values():
    data=load_requirements()
    assert 'SYNTHETIC' not in str(data)
    r=answer_requirements('What subjects for Finance domestic undergraduate?',data=data,today=TODAY)
    assert 'Mathematics + Geography' in r['answer']
    assert 'https://sdu.edu.kz/' in r['answer']
    r=answer_requirements('UNT score Computer Science domestic undergraduate',data=data,today=TODAY)
    assert r['requirement_status']=='unverified'
    r=answer_requirements('IELTS Computer Science domestic graduate',data=data,today=TODAY)
    assert r['requirement_status']=='unverified'


@pytest.mark.parametrize('output',[
    'You need 99 points and a fictional certificate.',
    '{"source":"faq","matched_id":"faq_language","answer":"invented 99"}',
    '{"source":"program","matched_id":"unknown"}',
    '{"source":"program","matched_id":"sdu-cs","answer":"invented 99"}',
    '{"source":"faq","matched_id":"faq_dorm","answer":"invented 99"}',
])
def test_ai_output_cannot_author_requirements(output,monkeypatch):
    from types import SimpleNamespace
    api=Mock()
    api.Client.return_value.chats.create.return_value.send_message.return_value.text=output
    monkeypatch.setattr(chatbot,'AI_AVAILABLE',True)
    monkeypatch.setenv('GEMINI_API_KEY','TEST-ONLY-FAKE-KEY')
    monkeypatch.setattr(chatbot,'genai',api,raising=False)
    monkeypatch.setattr(chatbot,'types',SimpleNamespace(GenerateContentConfig=Mock()),raising=False)
    r=chatbot.get_ai_fallback_response('An uncommon campus question', [], [])
    assert '99' not in r['answer']
    assert 'fictional' not in r['answer']
    api.Client.return_value.chats.create.return_value.send_message.assert_called_once()


@pytest.mark.parametrize('lang,under_review_word,missing_word', [
    ('en','under review','unavailable'),('ru','на рассмотрении','недоступны'),('kk','қарастырылуда','қолжетімсіз'),
])
def test_status_messages_in_all_languages(lang,under_review_word,missing_word,data):
    fields=data['sdu-cs']['requirements']['domestic']['undergraduate']
    fields['language']['status']='under_review'
    r=ask('IELTS Computer Science domestic undergraduate',data,language=lang)
    assert under_review_word in r['answer']
    assert not r['notification_available']
    del fields['language']
    assert missing_word in ask('IELTS Computer Science domestic undergraduate',data,language=lang)['answer']


def test_program_name_does_not_become_language_requirement(data):
    assert ask('Tell me about Two Foreign Languages',data) is None
    r=ask('Admission requirements Two Foreign Languages domestic undergraduate',data)
    assert r['context']['topics']==['exams','prerequisites','language']


def test_unrelated_query_cancels_pending_clarification(data):
    r=ask('IELTS',data)
    assert ask('How much does Computer Science cost?',data,r['context']) is None


def test_ielts_score_is_not_an_unt_question(data):
    r=ask('What IELTS score for Computer Science domestic undergraduate?',data)
    assert r['context']['topics']==['language']


def test_malicious_client_context_cannot_publish_a_value():
    r=client.post('/chat',json={
        'message':'undergraduate',
        'context':{'program_id':'sdu-cs','category':'domestic','topics':['exams'],
                   'pending':'study_level','status':'published','answer':'FAKE 199'},
    })
    assert r.status_code==200
    assert 'FAKE 199' not in r.json()['answer']
    assert r.json()['requirement_status'] != 'published'
