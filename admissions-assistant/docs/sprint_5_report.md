# Sprint 5 Final Report

**Project** — Smart University Admissions Assistant

**Scope** — Staff workspace for consultation analytics, catalog management, unanswered chat queries, and announcements.

## Delivered stories

| Story | Staff workflow | Acceptance evidence |
| --- | --- | --- |
| US6 · Staff Consultation Analytics | Open **Staff Analytics** for registrations, citizenship breakdown, recorded chat sessions, and the most saved programs. | Role checks, exact counts from seeded data, deterministic ranking, and empty states. |
| US10 · Staff Program Catalog Manager | Open **Manage Programs** to create, edit, or remove a program. Changes are read by the public catalog, chatbot, and calculators. | Manager and admin access, validation of invalid edits, and immediate propagation of fees and UNT thresholds. |
| US22 · Unanswered Chatbot Queries Log | Open **Manage FAQ** to search and filter unanswered questions, dismiss an entry, or convert it into a live FAQ answer. | Fallback capture, role checks, conversion, and an immediate FAQ-backed chatbot reply. |
| US23 · Staff Admissions Announcements | Open **Manage Announcements** to prepare a draft, publish, edit, deactivate, republish, or delete a notice. | Manager and admin access, validation, publishing to the public banner, and retention of inactive notices in the staff list. |

## Data and access

- The staff endpoints require an authenticated manager or admin. Analytics exposes counts and program names without individual applicant records. It counts applicant accounts across domestic, international, and unspecified citizenship. The top ten programs are ranked by distinct applicants who saved each one. The chat count covers all persisted sessions, including guest fallback sessions stored by the system.
- `GET /announcements` serves only published notices. A notice has a title, message, category, and optional HTTP(S) link. After a staff update, the API reflects the new state immediately. An open portal refreshes when it regains focus and every ten seconds while visible.
- Alembic revisions `003_program_min_unt_score` and `004_announcements` add the optional program threshold and the notices table. Apply `python -m alembic upgrade head` from the application directory before running with a migrated database.

## Reproduce acceptance tests

The Sprint 5 acceptance run passed 16 tests. The full suite passed 274 tests against a fresh installation from `requirements.txt`. An isolated SQLite database upgraded from revision `002_deadline_alerts` to `004_announcements` with its existing program record intact. Repeating the upgrade was a no-op.

From the application directory with the project dependencies installed:

```shell
python -m pytest -q tests/test_sprint_5_acceptance.py tests/test_us10_program_catalog.py tests/test_us22_unanswered_queries.py
python -m pytest -q
```

For a browser check, sign in as a manager. Verify the analytics cards, edit a program and confirm the new fee in the tuition calculator, convert an unanswered question and ask it again, then publish and deactivate an announcement while watching the public portal in another session. Check that an applicant cannot open the staff pages.

The schedule defers custom analytics date ranges, bulk catalog CSV import, automated clustering of unanswered questions, and scheduled announcement expiration.


## Saken's Sprint 5 verification — November 23, 2026

US6 was already in `main` in `2729544`. The existing acceptance tests cover
manager and admin access, applicant rejection, empty metrics, counts, and saved
program ranking. A separate check on a disposable database verified a manager's
counts and the 401/403 responses for anonymous users and applicants. It also
confirmed that the dashboard is present in the page HTML.

The US7 follow-up publishes guide version `2026-11-23.1`, due for review by
December 21. SDU's Bachelor page confirms the closed domestic dates and says
online state grant applications can be filed without the pedagogical examination
result. SDU's international page still lists November 30 for applications and
December 20 for originals for the spring intake. The Master route remains general.
Program-specific notes still follow their own review dates. The separate SDU
document and grant-list sync does not refresh this procedure guide.

- [SDU Bachelor admissions](https://sdu.edu.kz/en/admission-3-2/)
- [SDU International admissions](https://sdu.edu.kz/en/international-admissions/)
- [SDU Master admissions](https://sdu.edu.kz/en/master/)

The full suite passed 289 tests. With the real Almaty date, all 12 guide
combinations and the chat request passed. The review gate accepted the last
review day and withheld the guide the following day.
