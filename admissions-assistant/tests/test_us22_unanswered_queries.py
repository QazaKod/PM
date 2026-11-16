"""US22: Unanswered Chatbot Queries Log & One-Click FAQ Conversion Test Suite."""

import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.db_session import SessionLocal
from app.models import User
from app.security import hash_password, create_access_token


client = TestClient(app)


def _create_user(role: str = "admin") -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"us22_{role}_{uuid.uuid4().hex[:8]}@sdu.edu.kz",
            hashed_password=hash_password("Secret123!"),
            full_name=f"US22 {role.capitalize()}",
            role=role,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token({"sub": str(user.id), "role": user.role})
        return user, token
    finally:
        db.close()


def test_us22_rbac_permissions():
    """Only staff roles (manager/admin) can view, dismiss, or convert unanswered queries."""
    # Unauthenticated -> 401
    assert client.get("/admin/faqs/unanswered").status_code == 401
    assert client.post("/admin/faqs/unanswered/999999/dismiss").status_code == 401
    assert client.post("/admin/faqs/unanswered/999999/convert", json={"answer": "Test answer"}).status_code == 401

    # Applicant -> 403
    _, applicant_token = _create_user("applicant")
    app_headers = {"Authorization": f"Bearer {applicant_token}"}
    assert client.get("/admin/faqs/unanswered", headers=app_headers).status_code == 403
    assert client.post("/admin/faqs/unanswered/999999/dismiss", headers=app_headers).status_code == 403
    assert client.post("/admin/faqs/unanswered/999999/convert", json={"answer": "Test answer"}, headers=app_headers).status_code == 403

    # Manager and Admin -> 200
    _, manager_token = _create_user("manager")
    _, admin_token = _create_user("admin")
    assert client.get("/admin/faqs/unanswered", headers={"Authorization": f"Bearer {manager_token}"}).status_code == 200
    assert client.get("/admin/faqs/unanswered", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200


def test_us22_scenario1_convert_unanswered_to_faq_and_hot_reload():
    """US22 Scenario 1: Fallback questions appear in the staff log and convert to live FAQs."""
    _, applicant_token = _create_user("applicant")
    _, manager_token = _create_user("manager")
    app_headers = {"Authorization": f"Bearer {applicant_token}"}
    mgr_headers = {"Authorization": f"Bearer {manager_token}"}

    slug_a = f"hoverlockers_{uuid.uuid4().hex[:6]}"
    slug_b = f"skyshuttle_{uuid.uuid4().hex[:6]}"
    q_guest = f"How do {slug_a} work on campus?"
    q_auth = f"Can I bring my pet {slug_b} dinosaur?"

    # 1. Guest and authenticated fallback queries
    r_guest = client.post("/chat", json={"message": q_guest})
    assert r_guest.status_code == 200
    assert r_guest.json()["confident"] is False
    assert r_guest.json()["source"] is None

    r_auth = client.post("/chat", json={"message": q_auth}, headers=app_headers)
    assert r_auth.status_code == 200
    assert r_auth.json()["confident"] is False
    assert r_auth.json()["source"] is None

    # 2. Staff sees both in pending unanswered log
    list_res = client.get("/admin/faqs/unanswered?status=pending", headers=mgr_headers)
    assert list_res.status_code == 200
    pending_items = list_res.json()
    item_a = next((i for i in pending_items if i["question"] == q_guest), None)
    item_b = next((i for i in pending_items if i["question"] == q_auth), None)
    assert item_a is not None and item_a["status"] == "pending"
    assert item_b is not None and item_b["status"] == "pending"

    # 3. One-click convert endpoint (/unanswered/{id}/convert)
    new_answer = f"{slug_a} are available in Building A for all SDU students."
    conv_res = client.post(
        f"/admin/faqs/unanswered/{item_a['id']}/convert",
        json={"answer": new_answer, "category": "general"},
        headers=mgr_headers,
    )
    assert conv_res.status_code == 201
    conv_data = conv_res.json()
    assert conv_data["status"] == "converted"
    assert conv_data["query"]["status"] == "converted"
    assert conv_data["query"]["converted_faq_id"] == conv_data["faq"]["id"]

    # Query disappears from pending and appears in converted
    pending_after = client.get(f"/admin/faqs/unanswered?status=pending&search={slug_a}", headers=mgr_headers).json()
    assert pending_after == []
    converted_after = client.get(f"/admin/faqs/unanswered?status=converted&search={slug_a}", headers=mgr_headers).json()
    assert len(converted_after) == 1
    assert converted_after[0]["id"] == item_a["id"]

    # 4. Chatbot immediately answers the previously unanswered question!
    followup_res = client.post("/chat", json={"message": q_guest})
    assert followup_res.status_code == 200
    assert followup_res.json()["confident"] is True
    assert followup_res.json()["source"] == "faq"
    assert new_answer in followup_res.json()["answer"]

    # 5. Modal workflow via POST /admin/faqs with unanswered_query_id also marks query converted
    modal_answer = f"The {slug_b} pickup point is at the main campus gate."
    modal_res = client.post(
        "/admin/faqs",
        json={
            "question": q_auth,
            "answer": modal_answer,
            "category": "general",
            "keywords": [slug_b, "pickup"],
            "unanswered_query_id": item_b["id"],
        },
        headers=mgr_headers,
    )
    assert modal_res.status_code == 201
    pending_b = client.get(f"/admin/faqs/unanswered?status=pending&search={slug_b}", headers=mgr_headers).json()
    assert pending_b == []
    converted_b = client.get(f"/admin/faqs/unanswered?status=converted&search={slug_b}", headers=mgr_headers).json()
    assert len(converted_b) == 1
    assert converted_b[0]["converted_faq_id"] == modal_res.json()["id"]


def test_us22_scenario2_filter_and_dismiss_unanswered_queries():
    """US22 Scenario 2: Staff searches unanswered queries and dismisses irrelevant ones."""
    _, admin_token = _create_user("admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    spam_slug = f"spambot_{uuid.uuid4().hex[:6]}"
    keep_slug = f"validgap_{uuid.uuid4().hex[:6]}"
    q_spam = f"Buy cheap {spam_slug} gadgets on Mars?"
    q_keep = f"Can I park a submarine near {keep_slug} lake?"

    assert client.post("/chat", json={"message": q_spam}).json()["confident"] is False
    assert client.post("/chat", json={"message": q_keep}).json()["confident"] is False

    # Search filter finds only matching query
    filtered = client.get(f"/admin/faqs/unanswered?status=pending&search={spam_slug}", headers=headers).json()
    assert len(filtered) == 1
    spam_id = filtered[0]["id"]

    # Dismiss spam query
    dismiss_res = client.post(f"/admin/faqs/unanswered/{spam_id}/dismiss", headers=headers)
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["status"] == "dismissed"

    # Removed from pending, visible in dismissed, other query stays pending
    assert client.get(f"/admin/faqs/unanswered?status=pending&search={spam_slug}", headers=headers).json() == []
    dismissed_list = client.get(f"/admin/faqs/unanswered?status=dismissed&search={spam_slug}", headers=headers).json()
    assert len(dismissed_list) == 1 and dismissed_list[0]["id"] == spam_id

    kept_list = client.get(f"/admin/faqs/unanswered?status=pending&search={keep_slug}", headers=headers).json()
    assert len(kept_list) == 1 and kept_list[0]["question"] == q_keep


def test_us22_confident_answers_and_slot_clarifications_not_logged():
    """Normal confident responses and US3/US7 slot clarifications must NOT clutter the fallback log."""
    _, admin_token = _create_user("admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    unique_marker = f"notlogged_{uuid.uuid4().hex[:6]}"
    # Confident FAQ + Program + US3 clarification
    r_faq = client.post("/chat", json={"message": "What is the SPT Olympiad?"})
    assert r_faq.json()["confident"] is True

    r_prog = client.post("/chat", json={"message": "Tell me about the Software Engineering program"})
    assert r_prog.json()["confident"] is True

    r_req = client.post("/chat", json={"message": "What are the admission requirements for Computer Science?"})
    assert r_req.json()["source"] == "requirements"

    all_logged = client.get("/admin/faqs/unanswered?status=all", headers=headers).json()
    logged_questions = {item["question"] for item in all_logged}
    assert "What is the SPT Olympiad?" not in logged_questions
    assert "Tell me about the Software Engineering program" not in logged_questions
    assert "What are the admission requirements for Computer Science?" not in logged_questions
    assert unique_marker not in logged_questions


def test_us22_validation_and_not_found_errors():
    """Invalid convert payloads return 422 and missing query IDs return 404."""
    _, admin_token = _create_user("admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    assert client.post("/admin/faqs/unanswered/999999/dismiss", headers=headers).status_code == 404
    assert client.post(
        "/admin/faqs/unanswered/999999/convert",
        json={"answer": "Valid answer text"},
        headers=headers,
    ).status_code == 404

    assert client.post(
        "/admin/faqs/unanswered/999999/convert",
        json={"answer": "   "},
        headers=headers,
    ).status_code == 422


def test_us22_legacy_endpoint_fallback_and_patch_dismiss_and_custom_question():
    """Verify /chat/faq fallback logging, PATCH dismiss, and custom question override on convert."""
    _, manager_token = _create_user("manager")
    headers = {"Authorization": f"Bearer {manager_token}"}

    slug_patch = f"patchslug_{uuid.uuid4().hex[:6]}"
    slug_override = f"overrideslug_{uuid.uuid4().hex[:6]}"

    assert client.post("/chat/faq", json={"message": f"Can penguins eat {slug_patch}?"}).json()["confident"] is False
    assert client.post("/chat/programs", json={"message": f"Do astronauts ride {slug_override}?"}).json()["confident"] is False

    patch_item = client.get(f"/admin/faqs/unanswered?status=pending&search={slug_patch}", headers=headers).json()[0]
    patch_res = client.patch(f"/admin/faqs/unanswered/{patch_item['id']}/dismiss", headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "dismissed"

    conv_item = client.get(f"/admin/faqs/unanswered?status=pending&search={slug_override}", headers=headers).json()[0]
    conv_res = client.post(
        f"/admin/faqs/unanswered/{conv_item['id']}/convert",
        json={
            "question": f"What is the official policy for {slug_override}?",
            "answer": f"{slug_override} is handled by Student Affairs.",
            "category": "general",
        },
        headers=headers,
    )
    assert conv_res.status_code == 201
    assert conv_res.json()["faq"]["question"] == f"What is the official policy for {slug_override}?"
    assert conv_res.json()["query"]["status"] == "converted"
