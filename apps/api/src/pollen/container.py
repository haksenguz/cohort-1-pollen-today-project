"""Wiring.

FastAPI has no module system, so construction happens once here and the result
is put on the GraphQL context. Services take their dependencies as constructor
arguments exactly as they did under Nest, which keeps them testable without a
web request.
"""

from __future__ import annotations

from dataclasses import dataclass

from pollen.components.alerts.jobs.daily_alert import DailyAlertJob
from pollen.components.alerts.service import AlertsService
from pollen.components.alerts.telegram.sender import TelegramSender
from pollen.components.analytics.service import AnalyticsService
from pollen.components.forecast.service import ForecastService
from pollen.components.jobs.ops_notifier import OpsNotifier
from pollen.components.jobs.runner import JobRunner
from pollen.components.jobs.service import JobsService
from pollen.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    forecast: ForecastService
    analytics: AnalyticsService
    alerts: AlertsService
    jobs: JobsService
    runner: JobRunner
    telegram: TelegramSender
    daily_alert: DailyAlertJob


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()

    telegram = TelegramSender(settings)
    forecast = ForecastService()
    alerts = AlertsService()

    return Container(
        settings=settings,
        forecast=forecast,
        analytics=AnalyticsService(),
        alerts=alerts,
        jobs=JobsService(),
        runner=JobRunner(OpsNotifier(telegram, settings)),
        telegram=telegram,
        daily_alert=DailyAlertJob(forecast, alerts, telegram, settings),
    )
