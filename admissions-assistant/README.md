# Smart University Admissions Assistant

FastAPI + SQLAlchemy backend and a vanilla HTML/CSS/JavaScript interface for SDU admissions. The active frontend is **`admissions-assistant/static/`**, served by `app/main.py`; `static/config.json` selects the Steppe theme. The separate `theme-steppe/` directory is not served by this application.

Programs, FAQs, requirements, accounts, profiles and chat history are stored in SQLite, **not read directly from JSON on each request**. The default database is `data/app.db`. US7 procedures are an exception: the reviewed `data/admission_procedures.json` is read on every guide/API/chat request.

## Local setup (macOS/Linux, Python 3.12)

Run from the repository's `admissions-assistant/` directory. Python 3.12 is recommended for the pinned Pydantic wheels; the tested interpreter on this machine is:

```bash
cd /Users/maratsaken/Documents/PM/admissions-assistant
/Users/maratsaken/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p .demo
export DATABASE_URL="sqlite:///$PWD/.demo/admissions.db"
export LOG_FILE="$PWD/.demo/app.log"
export TESTING=1
export GEMINI_API_KEY=""
unset ADMISSION_GUIDE_FILE
.venv/bin/python scripts/migrate_to_sqlite.py --demo
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On another machine replace the long interpreter path with `python3.12`. Open [the application](http://127.0.0.1:8000) and [API documentation](http://127.0.0.1:8000/docs). If a server already occupies port 8000, use a different port. Stop with Ctrl+C.

## Normal startup, alternate port and stopping

For subsequent starts on this Mac, use the already installed environment and seeded demo database:

```bash
cd /Users/maratsaken/Documents/PM/admissions-assistant
export DATABASE_URL="sqlite:///$PWD/.demo/admissions.db"
export LOG_FILE="$PWD/.demo/app.log"
export TESTING=1
export GEMINI_API_KEY=""
unset ADMISSION_GUIDE_FILE
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If port 8000 is occupied, either use the application already running there or change the last command to:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open [http://127.0.0.1:8001](http://127.0.0.1:8001). Stop a server launched in your terminal with **Control+C** in that terminal. Unsetting `ADMISSION_GUIDE_FILE` selects the checked-in guide instead of an old test-file override. The database environment variable must remain set for every startup.

The `.venv/` and `.demo/` directories are ignored by Git. For subsequent starts, reuse the environment and database; the four `export` commands and the Uvicorn command are sufficient. Initialization is explicit: the server does not create or seed tables on startup. `init_db()` uses SQLAlchemy `create_all`, not a schema migration system; it does not upgrade old tables. Use a new demo database instead of changing an existing user's schema.

`migrate_to_sqlite.py --demo` creates tables and upserts the tracked legacy fixtures `programs.json.bak`, `faq.json.bak`, and `requirements.json.bak` (or corresponding `.json` files if present). Repeating the seed does not duplicate requirement rows. It requires an explicit separate SQLite `DATABASE_URL` and refuses `data/app.db`. Never point demo seeding at an existing real database: it updates catalog records. No admin account is needed for US7. `scripts/seed_admin.py` is an existing optional script with a fixed demo password; it is not run by this workflow.

**Legacy data warning:** the program/FAQ fixtures and US18/US19 calculations contain old prices, thresholds and heuristic grant labels. They are not verified current fees or statistical grant probabilities. They are outside Saken's US7 scope and must not be defended as current admissions advice. US7 does not use these numeric estimates.

## Optional external services

US7, program browsing, local chat matching and the local account workflows do not require a Gemini key. `TESTING=1` disables Telegram background polling in the demo. Leave external credentials unset for offline demonstrations. Email/SMS/Telegram delivery requires real provider configuration; automated tests stub those services. Demo registration can expose a debug verification code when delivery is not configured; use only synthetic local accounts. Existing `.env` settings may configure external providers, so check those settings before a real integration demo.

## Tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
.venv/bin/python scripts/validate_admission_guide.py data/admission_procedures.json
node --check static/app.js
```

Tests set `DATABASE_URL` **before app import**, create a temporary seeded database and stub AI and outbound messaging. They never seed the user database. `test_gemini.py` is a manual network diagnostic, protected by a main guard and excluded by `pytest.ini`.

## US7 guide

- `GET /admissions/guide?program_id=sdu-cs&category=domestic&level=undergraduate&lang=ru`
- Applicant category: `domestic` / `international`; level: `undergraduate` / `graduate`; language: `ru` / `kk` / `en`.
- `program_id` is optional. The seeded catalog has Bachelor programs only; Master currently offers a clearly labeled general route. Unknown programs, mismatched degrees and invalid parameters return 422.
- Expired, future-dated, malformed, incomplete or unreviewed procedures return 503 with no steps. The chatbot offers the admissions portal instead of substituting another applicant route.
- Past 2026 deadlines are visibly labeled as a closed cycle. The international Bachelor route distinguishes the published fall and spring periods; spring dates are not applied to the general Master route. Unknown deadlines are explicitly referred to admissions.
- The domestic Bachelor route adds a special examination action for teacher education and a creative-route confirmation for journalism before the grant step. International language assessment precedes the coordinator interview.
- Checkboxes persist in the current browser/device, keyed by version, applicant category, level and program. They are not evidence of an application submitted to SDU. A new version starts separate progress.

### Updating reviewed procedures

1. Admissions staff/reviewer checks the linked official sources, updates the relevant route and all three translations in a candidate JSON, increments `version`, and sets genuine `verified_on` / `review_due` dates. The review window cannot exceed 30 days. Do not merely extend a date without reviewing the policy.
2. Validate the candidate: `.venv/bin/python scripts/validate_admission_guide.py /absolute/path/candidate.json`.
3. Review its diff and publish it atomically on the same filesystem, preserving a copy of the previous version. For example, copy to `data/admission_procedures.next.json`, validate that file, back up the current catalog, then rename the validated candidate to `data/admission_procedures.json`.
4. Click **Refresh guide** or request the guide in chat. The next request reads the new file without restarting Uvicorn. Already displayed pages update on refresh, not by background push. For a separately managed policy file, set `ADMISSION_GUIDE_FILE` before starting the server.

This is the reviewed-data update workflow specified in the Trello US7 card. It does not automatically scrape or approve upstream university website changes. See [Sprint 3 report and 3–5 minute defense script](docs/sprint_3_report.md). Earlier US3 documentation describes the original JSON-era design and must be read together with the current SQLite implementation.

## Final acceptance audit

The independently tested previously published baseline is `6f7cf57ef73f22fa7ab1300c6ea0e378a1cd955a`. Its 157 tests passed in a clean environment, but additional acceptance checks found a complete-storage-denial startup failure and acceptance of whitespace-only procedure text. The final audited corrections add coverage; the finalization rerun passes 168 tests with 49 warnings, with no failures or skips. The broader Excel automatic-synchronization requirement remains unimplemented, and Master remains a general route. See [the Russian acceptance audit](docs/sprint_3_acceptance_audit.md) and the updated English Sprint 3 report for the exact scope, evidence and remaining requirements conflicts.

The clean install also emitted a yanked-release warning for the existing `google-genai==0.5.0` pin, citing Pillow vulnerability issues. `pip check` checks dependency compatibility, not security. The optional SDK was not upgraded during this US7 audit; review it separately before a production deployment.
