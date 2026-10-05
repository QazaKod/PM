import logging
import uuid
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.schemas import ChatQuery, ChatResponse
from app import chatbot, database
from app.db_session import engine, get_db
from app.models import User, ChatSession, ChatMessage
from sqladmin import Admin
from app.admin import (
    ProgramAdmin,
    FAQAdmin,
    RequirementAdmin,
    UserAdmin,
    ApplicantProfileAdmin,
    ChatSessionAdmin,
    LogsAdmin,
    AdminAuth,
)
from app.security import SECRET_KEY, get_optional_current_user
from app.routers import auth

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
    description="Intelligent Admissions Portal with RBAC, Chatbot, and SQLAdmin",
    version="0.2.0",
)

# Mount Routers
app.include_router(auth.router)

# Initialize SQLAdmin with secure authentication backend
admin_auth = AdminAuth(secret_key=SECRET_KEY)
admin = Admin(
    app,
    engine,
    title="Admissions DB Admin",
    templates_dir=str(TEMPLATES_DIR),
    authentication_backend=admin_auth,
)

# Register Admin Views
admin.add_view(ProgramAdmin)
admin.add_view(FAQAdmin)
admin.add_view(RequirementAdmin)
admin.add_view(UserAdmin)
admin.add_view(ApplicantProfileAdmin)
admin.add_view(ChatSessionAdmin)
admin.add_view(LogsAdmin)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log incoming chat requests
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
def chat(
    query: ChatQuery,
    optional_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Unified endpoint: routes to whichever knowledge base matches best, with optional user personalization."""
    logger.info(f"[Unified /chat] User Query: {query.message}")
    logger.info(f"[Unified /chat] Incoming Context: {query.context}")

    ctx_dict = query.context.model_dump() if query.context else {}

    # Personalization: If applicant is logged in, auto-fill profile details in requirements slots!
    if optional_user and optional_user.profile:
        prof = optional_user.profile
        if not ctx_dict.get("category") and prof.citizenship:
            ctx_dict["category"] = prof.citizenship
        if not ctx_dict.get("study_level") and prof.target_degree:
            ctx_dict["study_level"] = prof.target_degree

    response = chatbot.answer_query(
        query.message,
        ctx_dict if ctx_dict else None,
        query.language,
    )
    logger.info(f"[Unified /chat] Response Source: {response.get('source', 'None')} | Confident: {response.get('confident')}")
    logger.info(f"[Unified /chat] Outgoing Context: {response.get('context')}")

    # Persistence: If user is logged in, save chat history
    session_id = query.session_id
    if optional_user:
        session = None
        if session_id:
            session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == optional_user.id).first()
        if not session:
            session = ChatSession(
                id=str(uuid.uuid4()),
                user_id=optional_user.id,
                title=query.message[:40] + ("..." if len(query.message) > 40 else ""),
            )
            db.add(session)
            db.commit()
            session_id = session.id

        # Save user message
        db.add(ChatMessage(
            session_id=session.id,
            sender="user",
            message=query.message,
            context_state=ctx_dict,
        ))
        # Save bot response
        db.add(ChatMessage(
            session_id=session.id,
            sender="bot",
            message=response.get("answer", ""),
            source=response.get("source"),
            context_state=response.get("context"),
        ))
        db.commit()

    response["session_id"] = session_id
    return response


# Mount static assets and serve root SPA
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_root():
    return FileResponse(STATIC_DIR / "index.html")
