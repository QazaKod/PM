# Sprints 6 and 7

| Sprint | Story | Where to verify |
| --- | --- | --- |
| 6 | US2 Program recommendation | Enter interests and an academic goal in the program selector. The ranked matches come from the current catalog. |
| 6 | US12 Program comparison | Select two to four programs. Compare tuition, grant listings and recorded UNT thresholds side by side. Missing values are marked. |
| 6 | US24 Career pathways | Open Career & Internships or ask the assistant about a named program. Career roles are available for fourteen majors. The Computer Science card links to SDU's published graduate employment and median salary figures. Verified average starting salaries are still missing. |
| 6 | US25 Excel reports | A manager or administrator can download registrations or program statistics for a date range. Program inquiry counts cover stored answers attributed to a program. Historical messages without an attribution are excluded. |
| 7 | US11 Multilingual support | Choose English, Russian or Kazakh in the chat. Program answers, career guidance and the translated seed FAQs use the selected language. Source content is shown when a verified translation is unavailable. |
| 7 | US14 Escalation | Ask an unresolved question. The assistant identifies a departmental contact where possible and otherwise offers the admissions contact. |
| 7 | US26 Officer handoff | A signed-in applicant can request an officer. An available officer claims the conversation, reads its history and replies. When officers are offline, the request and contact details remain in the callback queue. |
| 7 | US27 Consultation rating | A signed-in applicant submits one rating per conversation and an optional comment. Managers see the average and can review low scores alongside the conversation. |

## Verification

Run `python -m alembic upgrade head` to apply revision `005_consultations`. Run `python -m pytest -q` for the full suite or `python -m pytest -q tests/test_sprints_6_7.py` for the sprint tests.

A browser check exercised program selection, comparison, a Russian career question, two-account handoff and replies, rating submission and an Excel download. The migration was applied to a fresh SQLite database.

Official admissions document requirements and grant listings refresh daily from the SDU admissions site. If the published tables cannot be validated, the portal retains the most recent validated snapshot and its date.
