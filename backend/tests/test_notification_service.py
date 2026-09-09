"""Notification rules: when an alert fires, and when it must stay quiet.

These are pure-function tests over stored preferences. No clock is waited on,
no scheduler is started, and nothing is ever sent — this project generates and
stores alerts only.
"""

from datetime import UTC, datetime

import pytest

from app.core.enums import AlertType, PollenLevel, RiskLevel
from app.models import NotificationPreference
from app.services import notification_service as ns
from app.services import risk


def _pref(**overrides) -> NotificationPreference:
    base = {
        "user_id": 1,
        "alert_pollen": True,
        "alert_air_quality": True,
        "alert_weather": True,
        "min_risk_level": "MODERATE",
        "quiet_hours_start": None,
        "quiet_hours_end": None,
    }
    base.update(overrides)
    return NotificationPreference(**base)


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 9, hour, 0, tzinfo=UTC)


# --- threshold -------------------------------------------------------------


@pytest.mark.parametrize(
    ("minimum", "actual", "expected"),
    [
        ("MODERATE", RiskLevel.LOW, False),
        ("MODERATE", RiskLevel.MODERATE, True),
        ("MODERATE", RiskLevel.HIGH, True),
        ("HIGH", RiskLevel.MODERATE, False),
        ("HIGH", RiskLevel.EMERGENCY, True),
        ("LOW", RiskLevel.LOW, True),
    ],
)
def test_risk_must_reach_the_users_minimum(minimum, actual, expected) -> None:
    pref = _pref(min_risk_level=minimum)
    assert ns.should_generate_alert(pref, AlertType.POLLEN, actual, _at(12)) is expected


# --- per-type toggles ------------------------------------------------------


def test_a_disabled_type_is_never_alerted() -> None:
    pref = _pref(alert_pollen=False)
    assert ns.should_generate_alert(pref, AlertType.POLLEN, RiskLevel.HIGH, _at(12)) is False
    # other types are unaffected
    assert ns.should_generate_alert(pref, AlertType.AIR_QUALITY, RiskLevel.HIGH, _at(12)) is True


def test_general_alerts_ignore_the_toggles() -> None:
    pref = _pref(alert_pollen=False, alert_air_quality=False, alert_weather=False)
    assert ns.should_generate_alert(pref, AlertType.GENERAL, RiskLevel.HIGH, _at(12)) is True


# --- quiet hours -----------------------------------------------------------


@pytest.mark.parametrize("hour", [23, 0, 3, 6])
def test_quiet_hours_wrapping_past_midnight_suppress(hour) -> None:
    pref = _pref(quiet_hours_start=22, quiet_hours_end=7)
    assert ns.should_generate_alert(pref, AlertType.POLLEN, RiskLevel.HIGH, _at(hour)) is False


@pytest.mark.parametrize("hour", [7, 12, 21])
def test_outside_wrapping_quiet_hours_alerts_fire(hour) -> None:
    pref = _pref(quiet_hours_start=22, quiet_hours_end=7)
    assert ns.should_generate_alert(pref, AlertType.POLLEN, RiskLevel.HIGH, _at(hour)) is True


def test_same_start_and_end_means_no_quiet_period() -> None:
    """Equal bounds are treated as 'unset', not as a 24-hour blackout."""
    pref = _pref(quiet_hours_start=9, quiet_hours_end=9)
    assert ns.should_generate_alert(pref, AlertType.POLLEN, RiskLevel.HIGH, _at(9)) is True


def test_a_half_configured_quiet_period_is_ignored() -> None:
    pref = _pref(quiet_hours_start=22, quiet_hours_end=None)
    assert ns.should_generate_alert(pref, AlertType.POLLEN, RiskLevel.HIGH, _at(23)) is True


# --- why the alert fired ---------------------------------------------------


def test_pollen_wins_when_it_matches_a_stored_allergy() -> None:
    env = risk.EnvInput(tree_pollen=PollenLevel.HIGH, pm25=5.0)
    assert ns.dominant_alert_type(env, {"TREE_POLLEN"}) == AlertType.POLLEN


def test_unrelated_pollen_does_not_claim_the_alert() -> None:
    """Grass is high, but this user only reacts to tree pollen."""
    env = risk.EnvInput(grass_pollen=PollenLevel.HIGH, pm25=40.0)
    assert ns.dominant_alert_type(env, {"TREE_POLLEN"}) == AlertType.AIR_QUALITY


def test_with_no_stored_allergies_any_pollen_counts() -> None:
    env = risk.EnvInput(weed_pollen=PollenLevel.MODERATE)
    assert ns.dominant_alert_type(env, set()) == AlertType.POLLEN


def test_falls_back_to_general_when_nothing_stands_out() -> None:
    env = risk.EnvInput(pm25=1.0, pm10=1.0, wind_speed=0.5)
    assert ns.dominant_alert_type(env, set()) == AlertType.GENERAL


def test_message_names_the_risk_level() -> None:
    env = risk.EnvInput(tree_pollen=PollenLevel.HIGH)
    message = ns.build_alert_message(RiskLevel.HIGH, AlertType.POLLEN, env)
    assert message
    assert isinstance(message, str)


# --- the scheduler must stay asleep in tests -------------------------------


def test_importing_the_service_does_not_start_the_scheduler() -> None:
    assert ns._scheduler is None
