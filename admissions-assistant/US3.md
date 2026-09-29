# US-3 — Admission Requirements FAQ (Saken)

## Implementation and scope

The original app had only an English FAQ answer and unverified `unt_subjects`
in program cards. There was no program/category/level requirements database,
conversation continuation, freshness check or subscription mechanism.
No AGENTS.md was present in the repository or its parent directory chain.
Routes are in `app/main.py`; the previously documented `app/api.py` does not exist.

US3 now runs before fuzzy US1/US5 matching on all three chat endpoints. It uses
exact names, curated English/Russian/Kazakh aliases and official program codes.
Ambiguous or unknown programs are clarified; no approximate program substitution
is allowed. Category and study level must also be known. An unknown name stays
unresolved; several recognized programs/categories prompt another clarification.

`data/requirements.json` is keyed by program ID, then
`requirements[domestic|international][undergraduate|graduate]`, then `exams`,
`prerequisites`, `language`. Each topic has publication status, official source,
check/verification dates, admission period, review deadline, internal validity
cutoff and three human-reviewed translations. IDs refer to the existing catalog;
US3 stores level-specific official codes. Incorrect existing undergraduate codes
were corrected in `programs.json` to avoid inconsistent selections.

Only `published` entries with supported official provenance, valid dates and the
requested translation can expose their text. Missing, unverified, under-review,
expired or malformed entries withhold their values. A field expires at the
earliest of `review_due`, `valid_until`, or 30 days after `verified_on`. An explicit
request for a different admission year is unverified. These cutoffs are internal
cache-safety rules, not university deadlines. The initial snapshot is restricted
to 2026 queries and must be reviewed before 2026-10-28; its internal hard cutoff
is 2026-12-31. This does not assert that admission is currently open.

The API returns typed `context` containing only program/category/level/topic,
language, optional requested year and the pending slot. The frontend sends it
with the next message; no user/session data is stored on the server. Reset chat
and page reload clear the context. Separate tabs and clients cannot share it.
A new full requirement request starts a new selection; a slot reply continues
the original topic. Explicit cost/document/dorm questions can leave clarification.
The language selector affects US3 only; multilingual US11 is not implemented.

The optional Gemini fallback selects existing program/FAQ IDs only. Generated
answer text is never displayed. It receives no US3 records or legacy UNT fields.
The legacy language FAQ no longer asserts unverified TOEFL/Foundation conditions.
Program cards link to the requirements chat instead of showing unverified subjects.
Legacy `sdu_admissions_guide.md`, `sdu_knowledge_base.json` and `unt_subjects` fields
are not authoritative US3 data and are not used to answer US3 queries.

## Official source verification — 2026-09-28

- [SDU undergraduate admissions](https://sdu.edu.kz/en/admission-3-2/): matched program
  names/codes and profile-subject groups; recorded school-leaver qualification
  and general English alternatives for applicable programs. Values are individual
  verified conditions, not an exhaustive list or an admission guarantee.
- [SDU international admissions](https://sdu.edu.kz/halykaralyk-kabyldau-komissyasy/):
  verified published previous-education and interview/test process for explicitly
  listed programs. These are shared international-route conditions, not inferred
  program-specific numerical thresholds. No UNT minimum is assumed.
- [Russian international page](https://sdu.edu.kz/ru/admission-dlya-inostrannyh-abiturientov/):
  differs in IELTS component detail; waiver and final enrollment certificate
  conditions require reconciliation. International language thresholds are
  deliberately unverified instead of combining potentially different conditions.
- [SDU master admissions](https://sdu.edu.kz/en/master/): identified exact graduate
  codes where names match. Requirements sit alongside mixed 2023/2025/2026 content
  and do not establish current program/category applicability. Graduate values
  remain unverified; undergraduate values are never reused.
- The undergraduate page links a [score PDF](https://drive.google.com/file/d/1WZV-cwI1ANP7Jm7zNI-LVSFk3JyE2rqx/view).
  The viewer exposed no readable table; a direct-download attempt also failed in
  the browsing tool. Numeric undergraduate thresholds were not imported.
- Journalism's legacy name/code cannot safely be mapped to the newer domestic
  program from these pages. Its requirements remain unverified. Null graduate
  codes indicate an unverified identity, not a claim that the program is offered.

No synthetic requirement is stored in production JSON. Tests use explicitly
labelled `SYNTHETIC` fixtures; they are never loaded by the application. No real
program is labelled `under_review` without official evidence.

## Updating and synchronization

No documented, stable, machine-readable policy feed was found in the inspected
sources. HTML pages mix admission periods and link external PDFs; locale versions
also differ. Unattended scraping cannot reliably approve requirements. Automatic
policy synchronization is therefore **not implemented**.

A maintainer should check sources at least monthly and before each intake:

1. Open the exact official program/category/level source and linked policy tables.
   Confirm the applicable intake, school/college route, grant/paid distinctions
   and program identity. Do not transfer another program's numbers.
2. For unavailable evidence use `unverified` (or omit the field). Use `under_review`
   only when the university actually says approval is pending. Do not label an
   inaccessible source as university review.
3. Compare locale versions, resolve conflicts with the university, translate all
   three answers, and have a second maintainer review the evidence and wording.
   Only then use `published`, `verified_on`, `checked_on`, `admission_period`,
   `review_due` (within 30 days) and an appropriate `valid_until`. Never advance
   dates merely to suppress expiration. The loader reads JSON per request, so no
   data restart is needed.
4. Run `venv/bin/python -m pytest -q`; manually ask at least one question per
   changed program/category/level and check the source links. Review the diff.

A future scheduled job could flag source-content changes for human review, but
must not auto-publish parsed scores. It needs a dependable source contract and an
operational scheduler before it can count as periodic synchronization.

## US3QATest notification gap

There is no notification backend, persistent subscriber store, sender, scheduler,
consent flow or delivery mechanism in this project. Under-review replies explicitly
say automatic notifications are unavailable and **no subscription was created**;
asking to be notified repeats that limitation. Actual notification offering and
delivery remain an **incomplete acceptance criterion**.

The smallest viable follow-up is an opt-in persistent subscription keyed by exact
program/category/level/topic, verified delivery address, consent and unsubscribe
token. After a reviewed publication, an idempotent job compares the prior status
and sends one availability message through a configured delivery provider; it
records delivery/failure and retries safely. This needs configured infrastructure
and tests for consent, duplicate delivery, expiry, unsubscribe and sender failures.
No email address is collected and no fake confirmation is shown in this change.

## Run and verification

Use Python 3.9–3.12 with the existing pinned dependencies; Python 3.14 failed to
build the pinned Pydantic core in this workspace. No dependency versions changed.

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Gemini is optional and not needed for US3. Existing
clients can still send `{"message":"..."}`. For continuation, send the returned
`context` unchanged with the next message; optional `language` is `en`, `ru` or `kk`.

Automated tests cover distinct questions and exact identities, categories, levels,
all languages, continuation, missing/review/expired/unverified values, invalid
provenance, new unknown programs, future periods, API validation/isolation, legacy
endpoints and US1/US5 regressions. External AI is mocked; no real AI call is made.
Browser checks exercised RU clarification → English slot replies → RU result,
Kazakh Finance prerequisites, international Management qualifications, unavailable
UNT/graduate values and unknown Medicine. UI reset was checked. Real notification
delivery, automated policy synchronization and live Gemini service are unverified.

## Instructor demonstration

Reset the chat between examples, leaving the language selector on Auto:

1. `Какой IELTS нужен?` → asks program; answer `Computer Science` → asks category;
   answer `domestic undergraduate` → Russian verified English alternatives and source.
2. `Қаржы бакалавриат Қазақстан үшін қандай пәндер керек?` → Kazakh Finance
   profile subjects, school-leaver scope and official source.
3. `What qualifications for Management international undergraduate?` → English
   published international-route qualification; additional prerequisites unverified.
4. `What UNT score for Computer Science domestic undergraduate?` → no invented
   score; explicitly unverified with source and check date.
5. `Какой IELTS для Computer Science, Казахстан, магистратура?` → graduate code
   and unverified current requirements; no borrowing undergraduate language scores.

Extra negative check: `What requirements for Medicine domestic undergraduate?`
asks for an exact known program and never returns Computer Science requirements.
After the review deadline, previously published values intentionally become outdated.
