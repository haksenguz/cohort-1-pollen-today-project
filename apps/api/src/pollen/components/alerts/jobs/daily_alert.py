"""The 07:00 KST morning alert. Slice C, Milestone 2.

Posts about TOMORROW, not today: slide 4 defines success as "finds out that
tomorrow will be a high-pollen day, in time to do something about it". Posting
about the current day gives a person no time to act. (Confirm with the mentor —
this is the one product detail the deck and the 07:00 timing do not pin down
between them.)

Every send is recorded through AlertsService, whose unique index makes a re-run
harmless. Re-running this job is therefore a safe operation, and proving that
live is what Milestone 2 grades.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pollen.components.alerts.dto import NewAlert
from pollen.components.alerts.message import build_alert_message
from pollen.components.alerts.service import AlertsService
from pollen.components.alerts.telegram.sender import TelegramSender
from pollen.components.forecast.service import ForecastService
from pollen.libs.enums import PollenType, risk_at_least
from pollen.libs.kst import kst_date_plus
from pollen.settings import Settings

log = logging.getLogger(__name__)

DAILY_ALERT_JOB = "daily-alert"


class DailyAlertJob:
    def __init__(
        self,
        forecast: ForecastService,
        alerts: AlertsService,
        telegram: TelegramSender,
        settings: Settings,
    ) -> None:
        self._forecast = forecast
        self._alerts = alerts
        self._telegram = telegram
        self._settings = settings

    async def execute(self) -> int:
        """Returns the number of alerts actually sent."""
        threshold = self._settings.alert_min_risk_level
        target_date = kst_date_plus(1)
        pollen_type = PollenType.WEEDS
        sent = 0

        for region, channel in self._settings.telegram_channels.items():
            forecast = self._forecast.three_day(region, pollen_type)
            day = next((d for d in forecast.days if d.date == target_date), None)

            if day is None:
                log.warning("%s: no forecast for %s, skipped", region, target_date)
                continue

            if not risk_at_least(day.risk_level, threshold):
                continue

            message_text = build_alert_message(
                region=region,
                pollen_type=pollen_type,
                risk_level=day.risk_level,
                target_date=target_date,
            )

            # Claim the slot BEFORE sending. If we sent first and then crashed,
            # the re-run would post a second time — the unique index only helps
            # if the write happens first.
            claimed = await self._alerts.record_delivery(
                NewAlert(
                    region=region,
                    pollen_type=pollen_type,
                    target_date=target_date,
                    risk_level=day.risk_level,
                    channel=channel,
                    sent_at=datetime.now(UTC),
                    message_text=message_text,
                )
            )

            if not claimed:
                log.info("%s: already sent for %s", region, target_date)
                continue

            await self._telegram.send(channel, message_text)
            sent += 1

        return sent
