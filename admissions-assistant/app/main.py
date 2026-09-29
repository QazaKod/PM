import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.schemas import ChatQuery, ChatResponse
from app import chatbot, database
from app.db_session import engine
from sqladmin import Admin
from app.admin import ProgramAdmin, FAQAdmin, RequirementAdmin, LogsAdmin

# Set up logging to file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
log_file = PROJECT_ROOT / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("admissions_api")

STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"

app = FastAPI(
    title="Smart University Admissions Assistant",
    description="Iteration 1: Chat-Program Info (US1) + Admission FAQ (US5)",
    version="0.1.0",
)

# Initialize SQLAdmin
admin = Admin(app, engine, title="Admissions DB Admin", templates_dir=str(TEMPLATES_DIR))
admin.add_view(ProgramAdmin)
admin.add_view(FAQAdmin)
admin.add_view(RequirementAdmin)
admin.add_view(LogsAdmin)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log incoming requests for the chatbot
    if request.url.path.startswith("/chat"):
        body_bytes = await request.body()
        logger.info(f"Incoming chat request from {request.client.host} | Body: {body_bytes.decode('utf-8')}")
    response = await call_next(request)
    return response


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
    """US1: Chat-Program Info."""
    logger.info(f"[Legacy /chat/programs] User Query: {query.message}")
    return chatbot.answer_query(query.message, query.context.model_dump() if query.context else None, query.language)


@app.post("/chat/faq", response_model=ChatResponse)
def chat_faq(query: ChatQuery):
    """US5: Admission FAQ."""
    logger.info(f"[Legacy /chat/faq] User Query: {query.message}")
    return chatbot.answer_query(query.message, query.context.model_dump() if query.context else None, query.language)


@app.post("/chat", response_model=ChatResponse)
def chat(query: ChatQuery):
    """Unified endpoint: routes to whichever knowledge base matches best."""
    logger.info(f"[Unified /chat] User Query: {query.message}")
    logger.info(f"[Unified /chat] Incoming Context: {query.context}")
    response = chatbot.answer_query(query.message, query.context.model_dump() if query.context else None, query.language)
    logger.info(f"[Unified /chat] Response Source: {response.get('source', 'None')} | Confident: {response.get('confident')}")
    logger.info(f"[Unified /chat] Outgoing Context: {response.get('context')}")
    return response


# Mount static assets and serve root SPA
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_root():
    return FileResponse(STATIC_DIR / "index.html")
