"""
Standalone Telegram Bot Worker (Phase 2 Remediation).
Allows running the Telegram Bot polling loop in an isolated worker process/container,
preventing multi-worker Uvicorn collisions.

Usage:
    python -m scripts.run_telegram_bot
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.telegram_service import start_telegram_polling


async def run_workers():
    from app.services.telegram_notifications import start_deadline_reminders
    tasks = [asyncio.create_task(start_telegram_polling()), asyncio.create_task(start_deadline_reminders())]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | [TelegramWorker] %(message)s",
    )
    os.environ["TELEGRAM_MODE"] = "polling"
    try:
        asyncio.run(run_workers())
    except KeyboardInterrupt:
        logging.info("Telegram worker stopped by user.")


if __name__ == "__main__":
    main()
