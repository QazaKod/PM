# Smart University Admissions Assistant — Iteration 1

Implements the first two user stories from the schedule:

- **US1 — Chat-Program Info**: ask questions about educational programs
- **US5 — Admission FAQ**: get answers to common admission questions

## Stack

FastAPI (Python) + JSON-backed knowledge base (`data/programs.json`,
`data/faq.json`) + a rule-based keyword-overlap matcher (`app/chatbot.py`).
No external NLP/AI service is used yet — this keeps Iteration 1 simple
and fully offline/testable, matching the "Volatility = Medium" tag on
both stories rather than committing early to a specific AI provider.

## Setup

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server runs at `http://127.0.0.1:8000`. Interactive API docs at
`http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /` — Single Page Application (Web Interface)
- `GET /programs` — Returns list of all academic programs (JSON)
- `GET /faq` — Returns list of all admission FAQs (JSON)
- `POST /chat/programs` — US1 only (program questions)
- `POST /chat/faq` — US5 only (FAQ questions)
- `POST /chat` — unified: tries both, returns whichever matches better

Request body: `{"message": "How much does Computer Science cost?"}`

Response: `{"answer": "...", "confident": true/false, "source": "program"|"faq"|null, "matched_id": "..."}`

When `confident` is `false`, the response is the fallback message that
offers to connect the user with admissions staff — this is Scenario 2
of both US1QATest and US5QATest.

## Running the QA tests

```bash
pytest tests/ -v
```

`tests/test_chatbot.py` maps 1:1 to the QA Test entries in the
schedule (US1QATest, US5QATest), including the "Pass: five different
questions answered correctly" and "Fail/fallback" scenarios.

## Known limitation (flag for Iteration 2 review)

The unified `/chat` endpoint picks whichever knowledge base (programs
vs FAQ) scores higher on keyword overlap. For a question like *"How
much does the IT program cost?"*, the generic FAQ cost-answer can
currently outscore the program-specific answer, because both share
words like "cost"/"how much". `/chat/programs` and `/chat/faq` always
give the correct, story-specific answer directly. Worth revisiting
the scoring weights (e.g. boosting program-name matches) before
demoing the unified endpoint.

## Next up (Iteration 2)

- US3 — Admission Requirements FAQ
- US4 — Required Documents Info
