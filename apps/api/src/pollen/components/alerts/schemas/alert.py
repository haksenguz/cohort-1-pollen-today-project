"""Persistence model for delivered alerts."""

from __future__ import annotations

from datetime import datetime

import pymongo
from beanie import Document

from pollen.libs.enums import PollenType, Region, RiskLevel


class AlertDoc(Document):
    region: Region
    pollen_type: PollenType
    #: The day the alert is *about*, not the day it was sent. ``YYYY-MM-DD`` KST.
    target_date: str
    risk_level: RiskLevel
    channel: str
    sent_at: datetime
    message_text: str

    class Settings:
        name = "alerts"
        indexes = [
            # THE IDEMPOTENCY GUARANTEE — see docs/adr/0003.
            #
            # A unique compound index means a second insert for the same
            # channel, region, pollen type and target date fails with E11000 at
            # the database. A re-run of the 07:00 job, or a scheduler restarted
            # mid-run, is harmless by construction.
            #
            # Deliberately not an application-level "already sent?" flag: that
            # is a check-then-act race, where two workers can both read "not
            # sent" before either writes. The database refuses the duplicate
            # however many processes race, so correctness stops depending on
            # our code being careful.
            pymongo.IndexModel(
                [
                    ("channel", pymongo.ASCENDING),
                    ("region", pymongo.ASCENDING),
                    ("pollen_type", pymongo.ASCENDING),
                    ("target_date", pymongo.ASCENDING),
                ],
                unique=True,
                name="uniq_alert_delivery",
            ),
            pymongo.IndexModel([("sent_at", pymongo.DESCENDING)], name="sent_at_desc"),
        ]
