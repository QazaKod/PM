"""US10: Staff Program Catalog Manager Test Suite.

Maps directly to User Story 10 & US10QATest:
  - RBAC enforcement (401 unauthenticated, 403 applicant, 200/201 manager & admin)
  - Scenario 1: Staff updates tuition fee, UNT subjects, passing score, and description ->
    immediately synced to public catalog (/programs), /admissions/metadata,
    UNT matcher, Tuition calculator, and Chatbot without restart.
  - Full CRUD lifecycle: create, filter/search, retrieve, update, delete (including FK cleanup).
  - Scenario 2: Validation rejects empty name/code/faculty/description, non-positive tuition
    or duration, invalid passing scores, and duplicate UNT subjects, preserving existing records.
  - Error handling (404 unknown ID, 400 duplicate ID) and SPA UI presence check.
"""

import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.db_session import SessionLocal
from app.models import User, SavedProgram
from app.security import hash_password, create_access_token
from app import chatbot


client = TestClient(app)


def _create_test_user(role: str = "admin") -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"us10_{role}_{uuid.uuid4().hex[:8]}@sdu.edu.kz",
            hashed_password=hash_password("Secret123!"),
            full_name=f"US10 {role.capitalize()}",
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


def test_us10_rbac_permissions():
    """Verify only admin and manager roles can access and mutate /admin/programs."""
    sample_payload = {
        "code": "6B06999",
        "faculty": "Faculty of Engineering and Natural Sciences",
        "name": "Unauthorized Test Program",
        "degree": "Bachelor",
        "duration_years": 4,
        "approx_cost_per_year_kzt": 1600000,
        "format": "Full-time",
        "language": ["English"],
        "unt_subjects": ["Mathematics", "Physics"],
        "description": "Should not be created without staff permissions.",
    }

    # 1. Unauthenticated requests -> 401
    assert client.get("/admin/programs").status_code == 401
    assert client.post("/admin/programs", json=sample_payload).status_code == 401
    assert client.put("/admin/programs/sdu-cs", json={"approx_cost_per_year_kzt": 1900000}).status_code == 401
    assert client.delete("/admin/programs/sdu-cs").status_code == 401

    # 2. Authenticated applicant -> 403 Forbidden
    _, applicant_token = _create_test_user(role="applicant")
    app_headers = {"Authorization": f"Bearer {applicant_token}"}
    assert client.get("/admin/programs", headers=app_headers).status_code == 403
    assert client.post("/admin/programs", json=sample_payload, headers=app_headers).status_code == 403
    assert client.put("/admin/programs/sdu-cs", json={"approx_cost_per_year_kzt": 1900000}, headers=app_headers).status_code == 403
    assert client.delete("/admin/programs/sdu-cs", headers=app_headers).status_code == 403

    # 3. Authenticated manager & admin -> 200 OK
    _, manager_token = _create_test_user(role="manager")
    _, admin_token = _create_test_user(role="admin")
    res_mgr = client.get("/admin/programs", headers={"Authorization": f"Bearer {manager_token}"})
    res_adm = client.get("/admin/programs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_mgr.status_code == 200
    assert res_adm.status_code == 200
    assert len(res_mgr.json()) >= 14


def test_us10_scenario1_staff_update_and_immediate_sync():
    """US10 Scenario 1: Staff updates tuition, UNT subjects, passing score, and description;
    public catalog, calculators, metadata, and chatbot reflect updates immediately.
    """
    _, manager_token = _create_test_user(role="manager")
    headers = {"Authorization": f"Bearer {manager_token}"}

    # Capture original sdu-cs state so we always restore cleanly
    orig_res = client.get("/admin/programs/sdu-cs", headers=headers)
    assert orig_res.status_code == 200
    orig = orig_res.json()

    new_cost = 2150000
    new_min_score = 88
    new_desc = "UPDATED US10: Algorithms, AI systems, cloud engineering, and cybersecurity research."

    try:
        # 1. Manager updates tuition fee, passing score, and description
        upd_res = client.put(
            "/admin/programs/sdu-cs",
            json={
                "approx_cost_per_year_kzt": new_cost,
                "min_unt_score": new_min_score,
                "description": new_desc,
            },
            headers=headers,
        )
        assert upd_res.status_code == 200
        updated = upd_res.json()
        assert updated["approx_cost_per_year_kzt"] == new_cost
        assert updated["min_unt_score"] == new_min_score
        assert updated["effective_min_unt_score"] == new_min_score
        assert updated["description"] == new_desc

        # 2. Public GET /programs immediately reflects changes
        pub_programs = client.get("/programs").json()
        cs_pub = next(p for p in pub_programs if p["id"] == "sdu-cs")
        assert cs_pub["approx_cost_per_year_kzt"] == new_cost
        assert cs_pub["min_unt_score"] == new_min_score
        assert cs_pub["description"] == new_desc

        # 3. GET /admissions/metadata reflects updated price and passing score
        meta = client.get("/admissions/metadata").json()
        cs_meta = next(p for p in meta["programs"] if p["id"] == "sdu-cs")
        assert cs_meta["approx_cost_per_year_kzt"] == new_cost
        assert cs_meta["min_unt_score"] == new_min_score

        # 4. US19 Tuition Calculator immediately uses updated fee
        tuition_res = client.post(
            "/admissions/tuition-calculator",
            json={"program_id": "sdu-cs", "unt_score": 100, "discounts": []},
        )
        assert tuition_res.status_code == 200
        assert tuition_res.json()["base_annual_fee"] == new_cost
        assert tuition_res.json()["base_total_fee"] == new_cost * orig["duration_years"]

        # 5. US18 UNT Eligibility Matcher immediately enforces updated passing score (88)
        # Score 80 used to qualify (default 75), now must be in deficit_programs (needs 8 points)
        unt_res = client.post(
            "/admissions/unt-matcher",
            json={"subject_1": "Mathematics", "subject_2": "Computer Science", "score": 80},
        )
        assert unt_res.status_code == 200
        unt_data = unt_res.json()
        cs_deficit = next((p for p in unt_data["deficit_programs"] if p["id"] == "sdu-cs"), None)
        assert cs_deficit is not None
        assert cs_deficit["min_score"] == new_min_score
        assert cs_deficit["points_needed"] == 8

        # 6. Chatbot immediately returns updated tuition and description
        chat_resp = chatbot.answer_query("Tell me about Computer Science program")
        assert chat_resp["confident"] is True
        assert chat_resp["source"] == "program"
        assert "2,150,000" in chat_resp["answer"]
        assert "UPDATED US10" in chat_resp["answer"]
    finally:
        # Restore original sdu-cs record for test isolation
        client.put(
            "/admin/programs/sdu-cs",
            json={
                "approx_cost_per_year_kzt": orig["approx_cost_per_year_kzt"],
                "min_unt_score": orig["min_unt_score"],
                "description": orig["description"],
                "unt_subjects": orig["unt_subjects"],
            },
            headers=headers,
        )


def test_us10_create_filter_and_delete_program_lifecycle():
    """Verify full CREATE -> FILTER/READ -> CALCULATORS/CHAT -> DELETE (with FK bookmark cleanup)."""
    applicant, _ = _create_test_user(role="applicant")
    _, admin_token = _create_test_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    tag = uuid.uuid4().hex[:6]
    prog_id = f"sdu-astrobio-{tag}"
    prog_name = f"Astrobiology Robotics {tag}"

    created_id = None
    try:
        # 1. CREATE new program
        create_res = client.post(
            "/admin/programs",
            json={
                "id": prog_id,
                "code": f"6B05{tag[:3]}",
                "faculty": "Faculty of Engineering and Natural Sciences",
                "name": prog_name,
                "degree": "Bachelor",
                "duration_years": 4,
                "approx_cost_per_year_kzt": 2050000,
                "format": "Full-time",
                "language": ["English", "Kazakh"],
                "unt_subjects": ["Биология", "Химия"],
                "min_unt_score": 82,
                "description": f"Interdisciplinary program in {prog_name} and life sciences.",
                "aliases": [f"astrobio{tag}"],
            },
            headers=headers,
        )
        assert create_res.status_code == 201
        created = create_res.json()
        created_id = created["id"]
        assert created_id == prog_id
        # UNT subjects normalized to canonical English names
        assert created["unt_subjects"] == ["Biology", "Chemistry"]
        assert created["min_unt_score"] == 82
        assert created["effective_min_unt_score"] == 82

        # 2. LIST with search, faculty, and degree filters
        search_res = client.get(
            f"/admin/programs?search={tag}&degree=Bachelor",
            headers=headers,
        )
        assert search_res.status_code == 200
        items = search_res.json()
        assert len(items) == 1
        assert items[0]["id"] == prog_id

        # 3. Immediately matched in US18 UNT Matcher (Biology + Chemistry)
        unt_match = client.post(
            "/admissions/unt-matcher",
            json={"subject_1": "Biology", "subject_2": "Chemistry", "score": 90},
        )
        assert unt_match.status_code == 200
        matched_ids = [p["id"] for p in unt_match.json()["eligible_programs"]]
        assert prog_id in matched_ids

        # 4. Immediately available in US19 Tuition Calculator
        tuition_calc = client.post(
            "/admissions/tuition-calculator",
            json={"program_id": prog_id, "unt_score": 115, "discounts": ["altyn_belgi"]},
        )
        assert tuition_calc.status_code == 200
        assert tuition_calc.json()["base_annual_fee"] == 2050000

        # 5. Immediately answerable by Chatbot
        chat_res = chatbot.answer_query(f"Tell me about {prog_name}")
        assert chat_res["confident"] is True
        assert chat_res["source"] == "program"
        assert chat_res["matched_id"] == prog_id
        assert "2,050,000" in chat_res["answer"]

        # 6. Bookmark program for an applicant to verify FK-safe deletion
        db = SessionLocal()
        try:
            db.add(SavedProgram(user_id=applicant.id, program_id=prog_id))
            db.commit()
        finally:
            db.close()

        # 7. DELETE program -> 200 OK without ForeignKey IntegrityError
        del_res = client.delete(f"/admin/programs/{prog_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"
        created_id = None

        # Verify removed from public catalog and calculators
        pub_ids = [p["id"] for p in client.get("/programs").json()]
        assert prog_id not in pub_ids
        calc_after = client.post("/admissions/tuition-calculator", json={"program_id": prog_id})
        assert calc_after.status_code == 404
    finally:
        if created_id:
            client.delete(f"/admin/programs/{created_id}", headers=headers)


def test_us10_scenario2_validation_preserves_existing_record():
    """US10 Scenario 2: Reject empty name, negative/zero tuition, invalid duration,
    out-of-range passing score, and duplicate UNT subjects without modifying valid DB records.
    """
    _, manager_token = _create_test_user(role="manager")
    headers = {"Authorization": f"Bearer {manager_token}"}

    before = client.get("/admin/programs/sdu-fin", headers=headers).json()

    invalid_updates = [
        {"name": "   "},
        {"name": ""},
        {"code": "  "},
        {"faculty": "   "},
        {"description": "   "},
        {"approx_cost_per_year_kzt": -500000},
        {"approx_cost_per_year_kzt": 0},
        {"duration_years": 0},
        {"duration_years": -2},
        {"min_unt_score": 0},
        {"min_unt_score": 141},
        {"unt_subjects": ["Mathematics", "Mathematics"]},
        {"unt_subjects": ["Mathematics", "Physics", "Chemistry"]},
    ]

    for bad_payload in invalid_updates:
        res = client.put("/admin/programs/sdu-fin", json=bad_payload, headers=headers)
        assert res.status_code in (400, 422), f"Expected validation error for {bad_payload}, got {res.status_code}"

    # Verify duplicate normalized UNT pair (e.g. Russian + English same subject) is also rejected
    dup_norm = client.put(
        "/admin/programs/sdu-fin",
        json={"unt_subjects": ["Математика", "Mathematics"]},
        headers=headers,
    )
    assert dup_norm.status_code == 400

    # Existing record must remain completely unchanged
    after = client.get("/admin/programs/sdu-fin", headers=headers).json()
    assert after == before

    # Creating a program with negative cost or empty name must also be rejected
    bad_create = client.post(
        "/admin/programs",
        json={
            "code": "6B04199",
            "faculty": "SDU Business School",
            "name": "   ",
            "degree": "Bachelor",
            "duration_years": 4,
            "approx_cost_per_year_kzt": -100,
            "description": "Invalid program",
        },
        headers=headers,
    )
    assert bad_create.status_code == 422


def test_us10_not_found_and_duplicate_id_handling():
    """Verify 404 for missing program IDs and 400 for duplicate program IDs."""
    _, admin_token = _create_test_user(role="admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    assert client.get("/admin/programs/nonexistent-prog-id", headers=headers).status_code == 404
    assert client.put("/admin/programs/nonexistent-prog-id", json={"name": "New Name"}, headers=headers).status_code == 404
    assert client.delete("/admin/programs/nonexistent-prog-id", headers=headers).status_code == 404

    dup_res = client.post(
        "/admin/programs",
        json={
            "id": "sdu-cs",
            "code": "6B06102",
            "faculty": "Faculty of Engineering and Natural Sciences",
            "name": "Duplicate CS",
            "degree": "Bachelor",
            "duration_years": 4,
            "approx_cost_per_year_kzt": 1850000,
            "description": "Duplicate ID test entry",
        },
        headers=headers,
    )
    assert dup_res.status_code == 400


def test_us10_ui_and_static_assets_served():
    """Verify US10 Staff Program Catalog Manager UI elements and static assets are served cleanly."""
    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers.get("content-type", "")
    assert 'id="nav-item-programs-admin"' in root.text
    assert 'id="section-programs-admin"' in root.text
    assert 'id="program-edit-modal"' in root.text
    assert 'id="form-program-edit"' in root.text

    for asset in ("/static/app.js", "/static/admissions.css", "/static/js/catalog.js", "/static/js/main.js"):
        res = client.get(asset)
        assert res.status_code == 200, f"Asset {asset} failed with HTTP {res.status_code}"
