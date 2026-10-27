"""001_initial_schema: Initial schema with RBAC, Programs, FAQs, Requirements, and Brute-Force Attempts.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-10-27 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.models import Base
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.models import Base
    Base.metadata.drop_all(bind=bind)
