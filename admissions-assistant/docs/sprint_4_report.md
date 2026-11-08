# Sprint 4 Final Report

**Project:** Smart University Admissions Assistant  
**Team:** Arman, Saken, Shadiyar, Yertai  
**Sprint Period:** October 26, 2026 – November 8, 2026  
**Repository:** [GitHub: QazaKod/PM](https://github.com/QazaKod/PM)  
**Status:** Completed & Delivered  
**Test Suite Status:** 246 / 246 PASSED (100% pass rate, exit code 0)  

---

## 1. Executive Summary

The primary objective of **Sprint 4** was to enhance applicant awareness and admissions office workflow through time-sensitive campaign tracking and knowledge base controls:
1. **US8 (Deadlines & Interactive Calendar):** Deliver a centralized calendar and milestone timeline for undergraduate and graduate admissions deadlines.
2. **US13 (FAQ Management Portal):** Empower admissions staff to create, update, and manage official FAQ entries with instant chatbot synchronization.
3. **US20 (Telegram Push Alerts):** Implement automated, scheduled Telegram reminder alerts dispatched to applicants prior to critical deadlines.
4. **Security & Bot Rework:** Strengthen Telegram authentication with 1-to-1 account binding, verified phone ownership, and self-service unlinking.

All sprint goals were achieved, verified with automated end-to-end tests, and integrated into the `main` branch.

---

## 2. Completed Scope & Deliverables

### 📅 US8 — Admissions Deadlines & Academic Calendar
- **Milestone Timeline:** Interactive timeline tracking all major admissions stages (State Grants, UNT testing periods, SPT Olympiad, creative exams, contract signing, and student dormitory applications).
- **Interactive Calendar Grid:** Month-by-month calendar view with color-coded day markers and detailed event flyout cards.
- **Multilingual & Filter Controls:** Multi-category filtering by degree level (Bachelor / Master), event category, and three languages (English, Kazakh, Russian).
- **Chatbot Deadline Recognition:** Natural language query routing enabling applicants to ask deadline questions directly in the chat in EN, RU, and KK.

### 📝 US13 — FAQ Database Management for Staff
- **Staff Administration Desk:** Role-based access control (RBAC: `admin`, `manager`) dedicated desk for managing the university's official FAQ library.
- **CRUD Operations:** Fast entry creation, full-text search, category tagging, keyword indexing, editing, and deletion.
- **Instant Hot-Reload:** Knowledge base updates immediately propagate to the AI chatbot without requiring application or server restarts.

### 🔔 US20 — Telegram Push Alerts & Reminder System
- **Scheduled Automated Reminders:** Background worker monitoring upcoming admissions milestones and notifying subscribed applicants **3 days and 1 day** before deadlines.
- **Durable Deduplication Ledger:** Database primary key claim system (`deadline_deliveries`) ensuring applicants never receive duplicate reminder notifications.
- **Quiet Hours Protection:** Automated suppression of notifications during night hours (**22:00 – 08:00 Almaty time / UTC+5**).
- **Direct Checklist Navigation:** Push notifications include inline Telegram buttons leading directly to the interactive admissions procedure guide on the portal.

### 🛡 Enhanced Telegram Authentication & Account Lifecycle
- **Cryptographic Deep Links:** Replaced plain codes in Telegram links with opaque, single-use `session_token` parameters (`?start=verify_<token>`).
- **Phone Ownership Verification:** Two-step handshake requiring Telegram native contact sharing (`request_contact: True`) to confirm the Telegram account matches the registered phone number.
- **Strict 1-to-1 Account Binding:** Enforces that one Telegram account links to exactly one applicant profile.
- **In-Bot Self-Service Management:** Applicants who changed numbers or lost old credentials can manage bindings directly in Telegram via `/unlink`, `/delete_account`, `/status`, and `/help`.

---

## 3. Quality Assurance & Testing

| Test Suite File | Test Count | Scope Verified | Status |
| :--- | :---: | :--- | :---: |
| `tests/test_sprint_4_acceptance.py` | 10 | Calendar boundary checks, Kazakh NLP, FAQ validation, alert dispatching | **PASSED** |
| `tests/test_telegram_auth_flow.py` | 16 | Contact sharing, phone validation, 1-to-1 binding, unlinking, reset protection | **PASSED** |
| `tests/test_us20_delivery.py` | 15 | Deduplication ledger, quiet hours, idempotency, concurrent delivery safety | **PASSED** |
| Existing Core & Regression Tests | 205 | Authentication, RBAC, calculators, guide, chatbot, SQLAdmin | **PASSED** |
| **Total Test Suite** | **246** | **Full system end-to-end integration** | **100% PASS** |

---

## 4. Next Sprint Outlook (Sprint 5)

With Sprint 4 delivered, the upcoming **Sprint 5 (November 9 – November 22, 2026)** will focus on applicant submissions and review:
- **US6:** Online Application Status Check.
- **US10:** Admission Information & Quota Updates for Staff.
- **US22:** Online Application Submission Portal with Unique Tracking Numbers.
- **US23:** Staff Application Review & Evaluation Desk.
