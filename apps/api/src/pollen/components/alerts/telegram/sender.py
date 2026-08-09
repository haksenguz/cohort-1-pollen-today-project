"""Posts a message to a Telegram chat or channel.

With no bot token configured it logs instead of sending, so the whole pipeline —
scheduler, forecast read, idempotency claim — can be exercised end to end before
the bot exists. A dry run that silently did nothing would be worse than useless,
so it says so at WARNING.
"""

from __future__ import annotations

import logging

import httpx

from pollen.libs.errors import UpstreamUnavailableError
from pollen.settings import Settings

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self._settings.telegram_bot_token)

    async def send(self, chat_id: str, text: str) -> None:
        token = self._settings.telegram_bot_token

        if not token:
            log.warning("DRY RUN (no bot token) -> %s\n%s", chat_id, text)
            return

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.post(
                    f"{TELEGRAM_API}/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "disable_web_page_preview": True,
                    },
                )
        except httpx.HTTPError as err:
            raise UpstreamUnavailableError(f"Telegram unreachable: {err}") from err

        if res.status_code != httpx.codes.OK:
            # Telegram puts the real reason in the body, not the status line.
            raise UpstreamUnavailableError(
                f"Telegram rejected the send: HTTP {res.status_code} {res.text[:200]}"
            )
