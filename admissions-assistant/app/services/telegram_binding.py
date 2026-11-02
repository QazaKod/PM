"""One-use authenticated website -> private Telegram chat linking."""
import hashlib
import secrets
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import TelegramBinding, User
from app.telegram_service import get_bot_username


def issue_link(db, user):
    token = secrets.token_urlsafe(24)
    binding = db.get(TelegramBinding, user.id)
    if binding is None:
        binding = TelegramBinding(user_id=user.id)
        db.add(binding)
    binding.token_hash = hashlib.sha256(token.encode()).hexdigest()
    binding.expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    return f"https://t.me/{get_bot_username()}?start=alerts_{token}"


def consume_link(db, token, chat_id):
    now = datetime.utcnow()
    try:
        # Lock / atomically invalidate the token before linking. Rollback on a
        # duplicate chat also restores the token; never take over another user.
        binding = db.query(TelegramBinding).filter(
            TelegramBinding.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            TelegramBinding.expires_at > now,
        ).with_for_update().first()
        if binding is None:
            return False
        user = db.get(User, binding.user_id)
        if user is None or not user.is_active or not user.is_verified:
            return False
        claimed = db.query(TelegramBinding).filter(
            TelegramBinding.user_id == user.id,
            TelegramBinding.token_hash == binding.token_hash,
        ).update({"token_hash": None, "expires_at": None}, synchronize_session=False)
        if not claimed:
            db.rollback()
            return False
        binding.chat_id = chat_id
        binding.verified_at = now
        user.telegram_chat_id = chat_id
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
