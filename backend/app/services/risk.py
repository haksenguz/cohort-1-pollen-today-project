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


def _pollen(level: PollenLevel | None) -> int:
    return _POLLEN_POINTS.get(level, 0) if level else 0


def score(env: EnvInput, user_allergens: set[str] | None = None) -> tuple[int, RiskLevel]:
    """Return (points, risk_level). Higher pollen for a known allergen weighs more."""
    pts = 0
    pts += max(_pollen(env.tree_pollen), _pollen(env.grass_pollen), _pollen(env.weed_pollen))

    if env.pm25 is not None and env.pm25 >= 35:
        pts += 2
    elif env.pm25 is not None and env.pm25 >= 15:
        pts += 1
    if env.pm10 is not None and env.pm10 >= 80:
        pts += 1
    if env.wind_speed is not None and env.wind_speed >= 5:
        pts += 1

    if user_allergens:
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
