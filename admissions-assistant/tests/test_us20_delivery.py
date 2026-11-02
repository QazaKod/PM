"""US20 acceptance: real DB claims, authenticated linking and mocked Telegram only."""
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_session import SessionLocal
from app.models import User, TelegramBinding, DeadlineDelivery
from app.security import create_access_token
from app.services import telegram_notifications as alerts, telegram_binding as links
from app import telegram_service

REAL_SEND = telegram_service.send_telegram_message
client = TestClient(app)
NOW = datetime(2026, 11, 2, 12, tzinfo=alerts.ALMATY_TZ)


def applicant(db, linked=True, **kwargs):
    user = User(email=uuid.uuid4().hex + '@example.test', full_name='Test <Applicant>',
                hashed_password='unused', is_active=True, is_verified=True,
                role='applicant', telegram_chat_id=uuid.uuid4().hex,
                telegram_notifications_enabled=True)
    for key, value in kwargs.items():
        setattr(user, key, value)
    db.add(user); db.commit()
    if linked:
        db.add(TelegramBinding(user_id=user.id, chat_id=user.telegram_chat_id, verified_at=datetime.utcnow()))
        db.commit()
    return user


@pytest.fixture
def calendar(monkeypatch):
    event = {'id': uuid.uuid4().hex, 'title': '<Grant & documents>',
             'date_start': '2026-11-01', 'date_end': '2026-11-05',
             'description': 'Submit <documents>', 'action_url': 'https://admissions.sdu.edu.kz',
             'alert_type': 'closing'}
    monkeypatch.setattr(alerts, 'get_upcoming_deadlines_for_alert', lambda **kwargs: [event])
    monkeypatch.setattr(telegram_service, 'is_telegram_configured', lambda: True)
    monkeypatch.setenv('PUBLIC_APP_URL', 'https://admissions.example.test')
    return event


def test_repeat_restart_and_offsets_do_not_duplicate(calendar, monkeypatch):
    calls = []
    monkeypatch.setattr(alerts, 'send_telegram_message', lambda c,t: calls.append(c) or True)
    with SessionLocal() as db:
        u=applicant(db);chat=u.telegram_chat_id
        alerts.send_deadline_alerts(db,3,reference_date=NOW)
    with SessionLocal() as db:
        alerts.send_deadline_alerts(db,3,force_send=True,reference_date=NOW)
        assert calls.count(chat)==1
        alerts.send_deadline_alerts(db,1,reference_date=NOW+timedelta(days=2))
        assert calls.count(chat)==2


def test_concurrent_workers_claim_once(calendar,monkeypatch):
    calls=[]
    monkeypatch.setattr(alerts,'send_telegram_message',lambda c,t:calls.append(c) or True)
    with SessionLocal() as db: chat=applicant(db).telegram_chat_id
    def run(_):
        with SessionLocal() as db: return alerts.send_deadline_alerts(db,3,reference_date=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run,range(2)))
    assert calls.count(chat)==1


@pytest.mark.parametrize('kwargs,linked', [({'is_active':False},True),({'is_verified':False},True),
    ({'telegram_notifications_enabled':False},True),({'role':'manager'},True),({},False)])
def test_ineligible_never_receives(calendar,monkeypatch,kwargs,linked):
    calls=[];monkeypatch.setattr(alerts,'send_telegram_message',lambda c,t:calls.append(c) or True)
    with SessionLocal() as db:
        chat=applicant(db,linked=linked,**kwargs).telegram_chat_id
        alerts.send_deadline_alerts(db,3,reference_date=NOW)
    assert chat not in calls


def test_unknown_delivery_not_retried(calendar,monkeypatch):
    calls=[]
    def timeout(c,t): calls.append(c); raise TimeoutError()
    monkeypatch.setattr(alerts,'send_telegram_message',timeout)
    with SessionLocal() as db:
        chat=applicant(db).telegram_chat_id
        alerts.send_deadline_alerts(db,3,reference_date=NOW)
        alerts.send_deadline_alerts(db,3,reference_date=NOW)
        row=db.query(DeadlineDelivery).filter_by(chat_id=chat,deadline_id=calendar['id']).one()
        assert row.state=='uncertain' and calls.count(chat)==1


def test_utc_clock_and_quiet_hour_catchup(calendar,monkeypatch):
    calls=[];monkeypatch.setattr(alerts,'send_telegram_message',lambda c,t:calls.append(c) or True)
    with SessionLocal() as db:
        chat=applicant(db).telegram_chat_id
        # 03:00 UTC is 08:00 Almaty; 02:59 UTC must not send.
        alerts.send_deadline_alerts(db,3,reference_date=datetime(2026,11,2,2,59,tzinfo=timezone.utc))
        assert chat not in calls
        alerts.send_deadline_alerts(db,3,reference_date=datetime(2026,11,2,3,tzinfo=timezone.utc))
        assert calls.count(chat)==1
    assert alerts.is_almaty_quiet_hours(datetime(2026,11,2,17,tzinfo=timezone.utc))


def test_html_and_actual_inline_keyboard(calendar,monkeypatch):
    captured=[]
    monkeypatch.setattr(telegram_service,'send_telegram_message',lambda *a,**kw:captured.append((a,kw)) or True)
    text=alerts.format_deadline_alert_html('<script>',calendar,3)
    assert '&lt;script&gt;' in text and '<script>' not in text
    assert '&lt;Grant &amp; documents&gt;' in text
    assert alerts.send_telegram_message('123',text)
    assert captured[0][1]['reply_markup']['inline_keyboard'][0][0]['url']=='https://admissions.example.test/#guide'


def test_secure_link_private_single_use_and_status():
    with SessionLocal() as db:
        u=applicant(db,linked=False);uid=u.id
    headers={'Authorization':'Bearer '+create_access_token({'sub':str(uid)})}
    assert client.post('/deadlines/telegram-link').status_code==401
    response=client.post('/deadlines/telegram-link',headers=headers)
    assert response.status_code==200
    token=response.json()['bot_url'].split('alerts_')[1]
    chat=str(int(uuid.uuid4().hex[:10],16))
    with SessionLocal() as db:
        assert db.get(TelegramBinding,uid).token_hash==hashlib.sha256(token.encode()).hexdigest()
        assert not links.consume_link(db,'wrong',chat)
        group={'message':{'chat':{'id':chat,'type':'group'},'from':{'id':chat},'text':'/start alerts_'+token}}
        assert telegram_service.process_telegram_update(group,db)['status']=='error'
        private={'message':{'chat':{'id':chat,'type':'private'},'from':{'id':chat},'text':'/start alerts_'+token}}
        assert telegram_service.process_telegram_update(private,db)['action']=='alerts_linked'
        assert not links.consume_link(db,token,chat)
    assert client.get('/deadlines/telegram-link',headers=headers).json()['linked']
    assert client.patch('/deadlines/preferences',headers=headers,json={'telegram_notifications_enabled':False}).json()['telegram_notifications_enabled'] is False


def test_expired_replaced_and_duplicate_chat_links():
    with SessionLocal() as db:
        owner=applicant(db);chat=owner.telegram_chat_id
        second=applicant(db,linked=False)
        old=links.issue_link(db,second).split('alerts_')[1]
        token=links.issue_link(db,second).split('alerts_')[1]
        assert not links.consume_link(db,old,'111')
        assert not links.consume_link(db,token,chat)
        binding=db.get(TelegramBinding,second.id)
        binding.expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
        assert not links.consume_link(db,token,'222')


def test_webhook_rejects_missing_wrong_secret(monkeypatch):
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET','secret')
    assert client.post('/auth/telegram-webhook',json={}).status_code==403
    assert client.post('/auth/telegram-webhook',json={},headers={'X-Telegram-Bot-Api-Secret-Token':'wrong'}).status_code==403
    assert client.post('/auth/telegram-webhook',json={},headers={'X-Telegram-Bot-Api-Secret-Token':'secret'}).status_code==200


def test_cycle_both_offsets_and_disabled(monkeypatch):
    monkeypatch.setattr(telegram_service,'is_telegram_configured',lambda:False)
    assert 'disabled' in alerts.run_reminder_cycle(NOW)
    monkeypatch.setattr(telegram_service,'is_telegram_configured',lambda:True)
    monkeypatch.setenv('PUBLIC_APP_URL','https://admissions.example.test')
    offsets=[]
    monkeypatch.setattr(alerts,'send_deadline_alerts',lambda db,days,**kw:offsets.append(days) or {})
    alerts.run_reminder_cycle(NOW)
    assert offsets==[3,1]


def test_background_loop_runs_cycle(monkeypatch):
    from unittest.mock import AsyncMock
    cycle=[]
    monkeypatch.setattr(alerts,'run_reminder_cycle',lambda:cycle.append(True))
    monkeypatch.setattr(alerts.asyncio,'sleep',AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError): asyncio.run(alerts.start_deadline_reminders())
    assert cycle==[True]


def test_transport_requires_telegram_ok_and_attaches_keyboard(monkeypatch):
    import httpx
    monkeypatch.setattr(telegram_service, 'send_telegram_message', REAL_SEND)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-only-token')
    payloads=[]
    def post(url,**kw):
        payloads.append(kw['json'])
        return httpx.Response(200,json={'ok':False})
    monkeypatch.setattr(telegram_service.httpx,'post',post)
    keyboard={'inline_keyboard':[[{'text':'Checklist','url':'https://example.test/#guide'}]]}
    assert telegram_service.send_telegram_message('123','Text',reply_markup=keyboard) is False
    assert payloads[0]['reply_markup']==keyboard
    monkeypatch.setattr(telegram_service.httpx,'post',lambda *a,**kw:httpx.Response(200,json={'ok':True}))
    assert telegram_service.send_telegram_message('123','Text') is True


def test_configuration_failure_creates_no_claim(calendar,monkeypatch):
    monkeypatch.setenv('PUBLIC_APP_URL','http://127.0.0.1:8000')
    with SessionLocal() as db:
        u=applicant(db)
        result=alerts.send_deadline_alerts(db,3,reference_date=NOW)
        assert result['dispatched']==0
        assert db.query(DeadlineDelivery).filter_by(chat_id=u.telegram_chat_id).count()==0


def test_only_exact_calendar_day_offsets_are_selected():
    from app.services.deadlines import get_upcoming_deadlines_for_alert
    from datetime import date
    closing=lambda days,ref: [d for d in get_upcoming_deadlines_for_alert(days,ref)
                              if d['date_end']=='2026-07-20' and d['alert_type']=='closing']
    assert closing(3,date(2026,7,17))
    assert closing(1,date(2026,7,19))
    assert not closing(3,date(2026,7,18))


def test_link_new_token_cannot_be_consumed_concurrently():
    with SessionLocal() as db:
        u=applicant(db,linked=False)
        token=links.issue_link(db,u).split('alerts_')[1]
    def consume(chat):
        with SessionLocal() as db: return links.consume_link(db,token,chat)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(consume,['777000111','777000222']))
    assert sum(results)==1
