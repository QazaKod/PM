"""
Standalone Long-Polling Telegram Bot Runner.
Works on localhost without needing a public domain, HTTPS, or ngrok!
"""
import os
import sys
import time
import logging
from pathlib import Path
import httpx

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db_session import SessionLocal
from app.telegram_service import (
    TELEGRAM_BOT_TOKEN,
    is_telegram_configured,
    process_telegram_update,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("telegram_bot_runner")


def run_bot_polling():
    if not is_telegram_configured():
        logger.error(
            "❌ TELEGRAM_BOT_TOKEN is not configured in .env!\n"
            "Please create a bot via @BotFather in Telegram, paste the token into .env, and re-run this script."
        )
        return

    from app.telegram_service import get_bot_token
    token = get_bot_token()
    base_url = f"https://api.telegram.org/bot{token}"

    # Verify bot credentials
    try:
        resp = httpx.get(f"{base_url}/getMe", timeout=10.0)
        bot_info = resp.json()
        if not bot_info.get("ok"):
            logger.error(f"❌ Invalid Telegram Bot Token: {bot_info.get('description')}")
            return
        bot_user = bot_info.get("result", {})
        logger.info(f"✅ Logged in as Telegram Bot: @{bot_user.get('username')} ({bot_user.get('first_name')})")
    except Exception as e:
        logger.error(f"❌ Connection error while contacting Telegram API: {e}")
        return

    # Delete existing webhook if any to allow polling
    try:
        httpx.post(f"{base_url}/deleteWebhook", timeout=5.0)
    except Exception:
        pass

    logger.info("👂 Listening for messages and password reset requests...")

    while True:
        try:
            url = f"{base_url}/getUpdates?offset={offset}&timeout=25"
            with httpx.Client(timeout=30.0) as client:
                res = client.get(url)
                if res.status_code != 200:
                    time.sleep(2)
                    continue

                data = res.json()
                updates = data.get("result", [])

                for update in updates:
                    update_id = update.get("update_id")
                    offset = update_id + 1

                    # Process update through our service with DB session
                    db = SessionLocal()
                    try:
                        result = process_telegram_update(update, db)
                        logger.info(f"📩 Handled update #{update_id}: {result}")
                    except Exception as err:
                        logger.error(f"⚠️ Error processing update #{update_id}: {err}")
                    finally:
                        db.close()

        except httpx.ReadTimeout:
            continue
        except KeyboardInterrupt:
            logger.info("🛑 Telegram Bot Polling stopped.")
            break
        except Exception as e:
            logger.error(f"⚠️ Polling loop error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    run_bot_polling()
