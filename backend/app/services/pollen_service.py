"""Pollen levels. Korea isn't covered by the keyless providers, so this uses a
keyed provider when configured and a clearly-marked sample otherwise.

Threshold bands are a prototype (grains/m3). Real bands belong in research/ once
a provider is chosen — see spec §8 ("AirKorea / suitable API").
"""

from dataclasses import dataclass

from app.core.enums import PollenLevel

# prototype grains/m3 cutoffs, provider-agnostic
_TREE = (15, 90)
_GRASS = (5, 20)
_WEED = (10, 50)


@dataclass
class PollenData:
    tree: PollenLevel | None = None
    grass: PollenLevel | None = None
    weed: PollenLevel | None = None
    is_sample: bool = False


def level_from_count(count: float | None, low_hi: tuple[int, int]) -> PollenLevel | None:
    if count is None:
        return None
    low, hi = low_hi
    if count > hi:
        return PollenLevel.HIGH
    if count >= low:
        return PollenLevel.MODERATE
    return PollenLevel.LOW


def parse_counts(tree: float | None, grass: float | None, weed: float | None) -> PollenData:
    return PollenData(
        tree=level_from_count(tree, _TREE),
        grass=level_from_count(grass, _GRASS),
        weed=level_from_count(weed, _WEED),
    )


def sample_pollen() -> PollenData:
    """Deterministic sample used until a Korea pollen provider is wired."""
    return PollenData(
        tree=PollenLevel.HIGH,
        grass=PollenLevel.MODERATE,
        weed=PollenLevel.LOW,
        is_sample=True,
    )


async def fetch_pollen(lat: float, lon: float, api_key: str = "") -> PollenData:
    if not api_key:
        return sample_pollen()
    # A keyed provider (Google Pollen, Ambee, ...) plugs in here and feeds
    # parse_counts(). Left unwired until the provider is chosen (TASKS Phase 1).
    return sample_pollen()
