"""US23 portal announcements.

Revision ID: 004_announcements
Revises: 003_program_min_unt_score
"""

from alembic import op
import sqlalchemy as sa

revision = "004_announcements"
down_revision = "003_program_min_unt_score"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("announcements"):
        return
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("link", sa.String(2083)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sqlite_autoincrement=True,
    )


def downgrade():
    if sa.inspect(op.get_bind()).has_table("announcements"):
        op.drop_table("announcements")
