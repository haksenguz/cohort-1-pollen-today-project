"""Deterministic environmental risk scoring (documentation §14).

Prototype scoring only — not a clinical instrument. Maps environmental
conditions plus a user's known allergens to a RiskLevel.
"""

from dataclasses import dataclass

from app.core.enums import PollenLevel, RiskLevel

_POLLEN_POINTS = {PollenLevel.HIGH: 3, PollenLevel.MODERATE: 1, PollenLevel.LOW: 0}


@dataclass
class EnvInput:
    tree_pollen: PollenLevel | None = None
    grass_pollen: PollenLevel | None = None
    weed_pollen: PollenLevel | None = None
    pm25: float | None = None
    pm10: float | None = None
    wind_speed: float | None = None
    # True when the pollen levels are the backend's hardcoded sample rather
    # than a reading from KMA. A sample is not a measurement: it must not add
    # points, and it must not stand in for pollen the provider never sent.
    pollen_is_sample: bool = False


def _pollen(level: PollenLevel | None) -> int:
    return _POLLEN_POINTS.get(level, 0) if level else 0


def has_data(env: EnvInput) -> bool:
    """True when at least one scored input is a real measurement.

    Every provider fails on its own, and a score built from nothing is zero
    points, which is LOW. That reads as "you are fine today" on a day when
    the app simply could not ask anybody. A caller that gets False must show
    no level at all.
    """
    if not env.pollen_is_sample and any(
        level is not None for level in (env.tree_pollen, env.grass_pollen, env.weed_pollen)
    ):
        return True
    return any(value is not None for value in (env.pm25, env.pm10, env.wind_speed))


def score(env: EnvInput, user_allergens: set[str] | None = None) -> tuple[int, RiskLevel]:
    """Return (points, risk_level). Higher pollen for a known allergen weighs more.

    A sampled pollen level contributes nothing. It is a placeholder for a
    reading that was never fetched, and scoring it as HIGH told the user
    "moderate" on the strength of a hardcoded number the note right below
    said was being withheld.
    """
    pts = 0
    sampled = env.pollen_is_sample
    if not sampled:
        pts += max(_pollen(env.tree_pollen), _pollen(env.grass_pollen), _pollen(env.weed_pollen))

    if env.pm25 is not None and env.pm25 >= 35:
        pts += 2
    elif env.pm25 is not None and env.pm25 >= 15:
        pts += 1
    if env.pm10 is not None and env.pm10 >= 80:
        pts += 1
    if env.wind_speed is not None and env.wind_speed >= 5:
        pts += 1

    if user_allergens and not sampled:
        pollen_map = {
            "TREE_POLLEN": env.tree_pollen,
            "GRASS_POLLEN": env.grass_pollen,
            "WEED_POLLEN": env.weed_pollen,
        }
        for allergen, level in pollen_map.items():
            if allergen in user_allergens and _pollen(level) >= 1:
                pts += 2
                break

    return pts, _to_level(pts)


def _to_level(points: int) -> RiskLevel:
    if points >= 6:
        return RiskLevel.HIGH
    if points >= 3:
        return RiskLevel.MODERATE
    return RiskLevel.LOW
