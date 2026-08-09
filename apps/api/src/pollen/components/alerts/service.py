from __future__ import annotations

import logging

from pymongo.errors import DuplicateKeyError

from pollen.components.alerts.dto import AlertDTO, NewAlert, PaginatedAlertDTO
from pollen.components.alerts.schemas.alert import AlertDoc
from pollen.libs.enums import Region

log = logging.getLogger(__name__)


class AlertsService:
    async def record_delivery(self, alert: NewAlert) -> bool:
        """Claim the right to send one alert, and record it.

        Returns False when this exact alert was already claimed — the normal
        outcome of a re-run, not an error. See ADR 0003.

        Insert first, never check first: a read-then-write has a race window
        between the two statements, and the unique index does not.
        """
        try:
            await AlertDoc(**alert.model_dump()).insert()
        except DuplicateKeyError:
            log.info(
                "duplicate suppressed: %s/%s/%s",
                alert.region,
                alert.pollen_type,
                alert.target_date,
            )
            return False
        return True

    async def history(self, region: Region | None, limit: int, offset: int) -> PaginatedAlertDTO:
        query = AlertDoc.find(AlertDoc.region == region) if region else AlertDoc.find_all()

        total = await query.count()
        docs = await query.sort(-AlertDoc.sent_at).skip(offset).limit(limit).to_list()

        return PaginatedAlertDTO(
            items=[
                AlertDTO(
                    id=str(d.id),
                    region=d.region,
                    pollen_type=d.pollen_type,
                    target_date=d.target_date,
                    risk_level=d.risk_level,
                    channel=d.channel,
                    sent_at=d.sent_at,
                    message_text=d.message_text,
                )
                for d in docs
            ],
            total=total,
            has_more=offset + len(docs) < total,
        )
