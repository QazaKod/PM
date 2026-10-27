import os
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from .models import Base

# By default, use SQLite in the data/ directory; in production, use PostgreSQL via DATABASE_URL
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

_raw_db_url = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/app.db")
# Normalize legacy postgres:// URL scheme to postgresql:// for SQLAlchemy 2.0
if _raw_db_url.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1)
else:
    SQLALCHEMY_DATABASE_URL = _raw_db_url


def build_engine(db_url: str):
    """Build SQLAlchemy engine configured for either PostgreSQL (QueuePool) or SQLite (WAL concurrency)."""
    if db_url.startswith("sqlite:"):
        eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 15},
        )

        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return eng

    # PostgreSQL / RDBMS production configuration with connection pooling
    return create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,
        pool_recycle=1800,
    )


# Create Engine
engine = build_engine(SQLALCHEMY_DATABASE_URL)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables in the database and ensure new columns exist."""
    Base.metadata.create_all(bind=engine)
    migrations = [
        "ALTER TABLE users ADD COLUMN telegram_notifications_enabled BOOLEAN DEFAULT 1",
        "ALTER TABLE faqs ADD COLUMN category VARCHAR DEFAULT 'general'",
        "ALTER TABLE account_verification_tokens ADD COLUMN attempts INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE password_reset_tokens ADD COLUMN attempts INTEGER DEFAULT 0 NOT NULL",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()


# Ensure schema tables and columns are created on initial load
init_db()


def get_db():
    """Dependency to get the DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
