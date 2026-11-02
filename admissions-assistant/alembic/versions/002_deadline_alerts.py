"""US20 durable Telegram bindings and delivery claims.

Revision ID: 002_deadline_alerts
Revises: 001_initial_schema
"""
from alembic import op
from app.models import TelegramBinding, DeadlineDelivery

revision = "002_deadline_alerts"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    # Existing installs may have initialized these through init_db/create_all.
    for model in (TelegramBinding, DeadlineDelivery):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in (DeadlineDelivery, TelegramBinding):
        model.__table__.drop(op.get_bind(), checkfirst=True)
