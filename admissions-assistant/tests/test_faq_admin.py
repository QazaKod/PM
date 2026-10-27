"""US13: Manage FAQ Database & Real-Time Hot-Reloading Test Suite."""

import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.db_session import SessionLocal
from app.models import User, FAQ
from app.security import hash_password, create_access_token
from app import chatbot


client = TestClient(app)


def _create_test_user(role: str = "admin") -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"{role}_{uuid.uuid4().hex[:8]}@sdu.edu.kz",
            hashed_password=hash_password("Secret123!"),
            full_name=f"Test {role.capitalize()}",
            role=role,
            is_active=True,
            is_verified=True,
            telegram_notifications_enabled=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token({"sub": str(user.id)})
        return user, token
    finally:
        db.close()


def test_faq_admin_rbac_permissions():
    """Verify unauthorized users cannot mutate FAQs."""
    # 1. Unauthenticated request -> 401
    res_unauth = client.get("/admin/faqs")
    assert res_unauth.status_code == 401

    res_post_unauth = client.post("/admin/faqs", json={
        "question": "Sample Question?",
        "answer": "Sample Answer",
    })
    assert res_post_unauth.status_code == 401

    # 2. Authenticated Applicant -> 403 Forbidden
    _, applicant_token = _create_test_user(role="applicant")
    res_applicant = client.get(
        "/admin/faqs",
        headers={"Authorization": f"Bearer {applicant_token}"}
    )
    assert res_applicant.status_code == 403

    # 3. Authenticated Manager & Admin -> 200 OK
    _, manager_token = _create_test_user(role="manager")
    res_manager = client.get(
        "/admin/faqs",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert res_manager.status_code == 200


def test_faq_crud_lifecycle_and_hot_reload():
    """Verify authorized staff CRUD operations and instant chatbot hot-reloading."""
    _, admin_token = _create_test_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    unique_keyword = f"zenithrobotics_{uuid.uuid4().hex[:6]}"
    unique_question = f"What is the {unique_keyword} club policy?"
    initial_answer = f"The {unique_keyword} club meets every Friday in Lab 304."

    # 1. CREATE FAQ
    create_payload = {
        "question": unique_question,
        "answer": initial_answer,
        "category": "clubs",
        "keywords": [unique_keyword, "robotics", "friday", "lab 304"],
    }
    create_res = client.post("/admin/faqs", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    created_faq = create_res.json()
    faq_id = created_faq["id"]
    assert created_faq["question"] == unique_question
    assert created_faq["category"] == "clubs"

    # 2. HOT-RELOAD CHECK: Chatbot must answer immediately without server restart!
    chat_resp = chatbot.answer_query(f"tell me about {unique_keyword}")
    assert chat_resp["source"] == "faq"
    assert chat_resp["confident"] is True
    assert initial_answer in chat_resp["answer"]

    # Public /faq endpoint must also return the new entry
    faq_list_res = client.get("/faq")
    assert faq_list_res.status_code == 200
    all_faqs = faq_list_res.json()
    assert any(f["id"] == faq_id for f in all_faqs)

    # 3. READ FAQ via Admin API with filtering
    admin_list = client.get(f"/admin/faqs?search={unique_keyword}", headers=headers)
    assert admin_list.status_code == 200
    matched = admin_list.json()
    assert len(matched) == 1
    assert matched[0]["id"] == faq_id

    # 4. UPDATE FAQ
    updated_answer = f"UPDATED: The {unique_keyword} club now meets on Saturday in Hall A."
    update_payload = {
        "answer": updated_answer,
        "keywords": [unique_keyword, "robotics", "saturday", "hall a"],
    }
    update_res = client.put(f"/admin/faqs/{faq_id}", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["answer"] == updated_answer

    # HOT-RELOAD CHECK: Chatbot must serve the updated answer immediately!
    chat_updated_resp = chatbot.answer_query(f"when does {unique_keyword} meet")
    assert chat_updated_resp["source"] == "faq"
    assert updated_answer in chat_updated_resp["answer"]

    # 5. DELETE FAQ
    del_res = client.delete(f"/admin/faqs/{faq_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify deleted from public /faq
    faq_list_after = client.get("/faq").json()
    assert not any(f["id"] == faq_id for f in faq_list_after)


def test_faq_validation():
    """Verify validation errors for empty fields (HTTP 422)."""
    _, admin_token = _create_test_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Empty question -> 422
    res_empty_q = client.post("/admin/faqs", json={
        "question": "   ",
        "answer": "Valid answer",
    }, headers=headers)
    assert res_empty_q.status_code == 422

    # Empty answer -> 422
    res_empty_a = client.post("/admin/faqs", json={
        "question": "Valid question?",
        "answer": "   ",
    }, headers=headers)
    assert res_empty_a.status_code == 422


def test_us13_scenario1_manager_crud_lifecycle_and_hot_reload():
    """US13 Scenario 1: Staff manager creates, edits, and deletes FAQ entry with instant chatbot hot-reload."""
    _, manager_token = _create_test_user(role="manager")
    headers = {"Authorization": f"Bearer {manager_token}"}

    unique_kw = f"quantum_{uuid.uuid4().hex[:6]}"
    q_text = f"How to enroll in {unique_kw} studies?"
    ans_text = f"Initial answer for {unique_kw} studies via Manager."

    # 1. Manager CREATE FAQ
    create_res = client.post("/admin/faqs", json={
        "question": q_text,
        "answer": ans_text,
        "category": "academics",
        "keywords": [unique_kw, "quantum", "manager"],
    }, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    faq_id = created["id"]

    # Hot-reload verification: Chatbot answers immediately
    resp_init = chatbot.answer_query(f"enroll in {unique_kw}")
    assert resp_init["source"] == "faq"
    assert resp_init["confident"] is True
    assert ans_text in resp_init["answer"]

    # 2. Manager EDIT FAQ
    updated_ans = f"Updated answer for {unique_kw} studies after curriculum revision."
    update_res = client.put(f"/admin/faqs/{faq_id}", json={
        "answer": updated_ans,
    }, headers=headers)
    assert update_res.status_code == 200

    # Hot-reload verification: Chatbot returns updated answer immediately
    resp_updated = chatbot.answer_query(f"enroll in {unique_kw}")
    assert resp_updated["source"] == "faq"
    assert updated_ans in resp_updated["answer"]

    # 3. Manager DELETE FAQ
    del_res = client.delete(f"/admin/faqs/{faq_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify hot-reload removed it from chatbot knowledge
    faq_check = client.get("/faq").json()
    assert not any(f["id"] == faq_id for f in faq_check)


def test_us13_scenario2_applicant_and_unauth_modifications_rejected():
    """US13 Scenario 2: Unauthorized applicant user or unauthenticated request attempts to modify FAQ database."""
    # 1. Unauthenticated attempts -> 401
    assert client.post("/admin/faqs", json={"question": "Q?", "answer": "A"}).status_code == 401
    assert client.put("/admin/faqs/some_id", json={"answer": "A"}).status_code == 401
    assert client.delete("/admin/faqs/some_id").status_code == 401

    # 2. Authenticated applicant attempts -> 403 Forbidden
    _, app_token = _create_test_user(role="applicant")
    app_headers = {"Authorization": f"Bearer {app_token}"}
    assert client.post("/admin/faqs", json={"question": "Q?", "answer": "A"}, headers=app_headers).status_code == 403
    assert client.put("/admin/faqs/some_id", json={"answer": "A"}, headers=app_headers).status_code == 403
    assert client.delete("/admin/faqs/some_id", headers=app_headers).status_code == 403

