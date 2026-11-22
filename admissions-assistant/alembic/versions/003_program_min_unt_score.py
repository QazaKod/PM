"""US10 add optional staff-managed min_unt_score column to programs.

Revision ID: 003_program_min_unt_score
Revises: 002_deadline_alerts
"""
from alembic import op
import sqlalchemy as sa

revision = "003_program_min_unt_score"
down_revision = "002_deadline_alerts"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "programs" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("programs")}
        if "min_unt_score" not in columns:
            op.add_column("programs", sa.Column("min_unt_score", sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "programs" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("programs")}
        if "min_unt_score" in columns:
            with op.batch_alter_table("programs") as batch_op:
                batch_op.drop_column("min_unt_score")
