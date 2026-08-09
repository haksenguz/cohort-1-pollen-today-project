"""Failure notifications to the private ops channel.

Separate from alert delivery on purpose: an ops message is for us, is never
idempotency-checked, and must never be confused with something a subscriber
sees.
"""

from __future__ import annotations

import logging

from pollen.components.alerts.telegram.sender import TelegramSender
from pollen.settings import Settings

log = logging.getLogger(__name__)


class OpsNotifier:
    def __init__(self, telegram: TelegramSender, settings: Settings) -> None:
        self._telegram = telegram
        self._settings = settings

    async def job_failed(self, job_name: str, error: str) -> None:
        chat_id = self._settings.telegram_ops_chat_id

        if not chat_id:
            log.warning("no TELEGRAM_OPS_CHAT_ID set — %s failure not reported", job_name)
            return

        await self._telegram.send(chat_id, f"⚠️ {job_name} failed\n\n{error}")
