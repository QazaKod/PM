"""Consultation queue, availability, routing settings and session ratings."""
from alembic import op
from app.models import OfficerPresence, OfficerRequest, SessionRating, ConsultationSetting

revision = "005_consultations"
down_revision = "004_announcements"
branch_labels = None
depends_on = None

tables = [OfficerPresence, OfficerRequest, SessionRating, ConsultationSetting]


def upgrade():
    for model in tables:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in reversed(tables):
        model.__table__.drop(op.get_bind(), checkfirst=True)
