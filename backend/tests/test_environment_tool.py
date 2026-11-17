"""The get_today_environment tool: read-only, server-located, honest refusals."""

import pytest

from app.agents import symptom_agent as sa


def _origin() -> sa.NearbyCareOrigin:
    return sa.NearbyCareOrigin(latitude=37.5, longitude=127.0)


def _snapshot(available: bool = True):
    def fetch(_origin):
        return sa.EnvironmentSnapshot(
            pollen={"tree": "high", "grass": "low", "weed": None},
            air_quality={"pm25": 12.0, "pm10": 30.0},
            weather={"temperature": 18.0, "humidity": 40.0, "wind": 2.0},
            available=available,
        )

    return fetch


def test_returns_conditions_for_the_saved_location():
    tool = sa.build_environment_tool(_origin(), snapshot=_snapshot())
    result = tool.execute({})
    assert result["pollen"]["tree"] == "high"
    assert result["air_quality"]["pm25"] == 12.0


def test_no_saved_location_refuses_plainly():
    tool = sa.build_environment_tool(None, snapshot=_snapshot())
    with pytest.raises(sa.ToolRefused) as exc:
        tool.execute({})
    assert exc.value.code == sa.NO_LOCATION


def test_every_provider_down_refuses_instead_of_reporting_clear_air():
    tool = sa.build_environment_tool(_origin(), snapshot=_snapshot(available=False))
    with pytest.raises(sa.ToolRefused) as exc:
        tool.execute({})
    assert exc.value.code == sa.PROVIDER_UNAVAILABLE


def test_tool_is_registered_in_the_shipped_registry():
    registry = sa.default_tool_registry(_origin())
    assert sa.ENVIRONMENT_TOOL in registry.names()
