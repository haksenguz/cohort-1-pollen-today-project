"""The drift guard.

Python cannot generate enums from SDL the way the TypeScript side does, so
``libs/enums.py`` is hand-written. This test parses the real SDL and fails if
the two ever disagree — it is the reason hand-writing them is acceptable.

Do not delete it. Without it, adding a region to the schema and forgetting the
Python side is a silent bug that only appears when someone queries that region.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pollen.libs.enums import REGION_AREA_NO, JobStatus, PollenType, Region, RiskLevel

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"

ENUM_BLOCK = re.compile(r"enum\s+(\w+)\s*\{([^}]*)\}", re.MULTILINE)


def sdl_enums() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in SCHEMA_DIR.glob("*.graphql"):
        for name, body in ENUM_BLOCK.findall(path.read_text(encoding="utf-8")):
            values = {
                line.strip()
                for line in body.splitlines()
                if line.strip() and not line.strip().startswith(("#", '"'))
            }
            found[name] = values
    return found


@pytest.mark.parametrize(
    ("sdl_name", "python_enum"),
    [
        ("RiskLevel", RiskLevel),
        ("PollenType", PollenType),
        ("Region", Region),
        ("JobStatus", JobStatus),
    ],
)
def test_python_enum_matches_sdl(sdl_name: str, python_enum: type) -> None:
    declared = sdl_enums()
    assert sdl_name in declared, f"{sdl_name} is not declared in any .graphql file"
    assert {m.value for m in python_enum} == declared[sdl_name]


def test_every_region_has_an_area_no() -> None:
    """A region with no areaNo cannot be fetched from KMA — see ADR 0005."""
    assert set(REGION_AREA_NO) == set(Region)


def test_area_numbers_are_ten_digit_codes() -> None:
    for region, area_no in REGION_AREA_NO.items():
        assert re.fullmatch(r"\d{10}", area_no), f"{region} has a malformed areaNo"
