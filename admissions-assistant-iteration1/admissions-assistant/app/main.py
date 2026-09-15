from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.schemas import ChatQuery, ChatResponse
from app import chatbot, database

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Smart University Admissions Assistant",
    description="Iteration 1: Chat-Program Info (US1) + Admission FAQ (US5)",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/programs")
def get_programs():
    """US1: Return all available academic programs."""
    return database.load_programs()


@app.get("/faq")
def get_faq():
    """US5: Return all admission FAQ entries."""
    return database.load_faq()


@app.post("/chat/programs", response_model=ChatResponse)
def chat_programs(query: ChatQuery):
    """US1 — Chat-Program Info."""
    return chatbot.answer_program_query(query.message)


@app.post("/chat/faq", response_model=ChatResponse)
def chat_faq(query: ChatQuery):
    """US5 — Admission FAQ."""
    return chatbot.answer_faq_query(query.message)


@app.post("/chat", response_model=ChatResponse)
def chat(query: ChatQuery):
    """Unified endpoint: routes to whichever knowledge base matches best."""
    return chatbot.answer_query(query.message)


# Mount static assets and serve root SPA
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_root():
    return FileResponse(STATIC_DIR / "index.html")

