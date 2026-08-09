"""The shared enums.

These are DECLARED in ``schema/common.graphql``. Python cannot generate enums
from SDL the way the TypeScript side does, so they are written out here — and
``tests/test_schema_enums.py`` parses the SDL and fails if the two disagree.
That test is what keeps this file honest; do not delete it.
"""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    """The four levels published daily by KMA. Ordered low to very high."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class PollenType(StrEnum):
    OAK = "OAK"
    PINE = "PINE"
    WEEDS = "WEEDS"


class Region(StrEnum):
    """The 16 top-level 시/도, from the KMA DFS zone tree. See ADR 0005."""

    SEOUL = "SEOUL"
    BUSAN = "BUSAN"
    DAEGU = "DAEGU"
    INCHEON = "INCHEON"
    DAEJEON = "DAEJEON"
    ULSAN = "ULSAN"
    SEJONG = "SEJONG"
    GWANGJU_JEONNAM = "GWANGJU_JEONNAM"
    GYEONGGI = "GYEONGGI"
    GANGWON = "GANGWON"
    CHUNGBUK = "CHUNGBUK"
    CHUNGNAM = "CHUNGNAM"
    JEONBUK = "JEONBUK"
    GYEONGBUK = "GYEONGBUK"
    GYEONGNAM = "GYEONGNAM"
    JEJU = "JEJU"


class JobStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"


#: Ordering is semantic — ``risk_at_least`` depends on it, so do not sort.
RISK_LEVELS_ORDERED: tuple[RiskLevel, ...] = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.VERY_HIGH,
)


def risk_at_least(level: RiskLevel, threshold: RiskLevel) -> bool:
    """True when ``level`` is at or above ``threshold``. Drives the alert cutoff."""
    return RISK_LEVELS_ORDERED.index(level) >= RISK_LEVELS_ORDERED.index(threshold)


#: Region -> the ``areaNo`` the KMA endpoints accept. Source: DFS zone tree,
#: filtered to rows whose 행정구역코드 ends in 00000000. See ADR 0005.
#:
#: 1200000000 is 전남광주통합특별시 — Gwangju and Jeollanam-do merged, and the
#: zone tree has no separate 전라남도 row. The old Gwangju code returns nothing.
REGION_AREA_NO: dict[Region, str] = {
    Region.SEOUL: "1100000000",
    Region.GWANGJU_JEONNAM: "1200000000",
    Region.BUSAN: "2600000000",
    Region.DAEGU: "2700000000",
    Region.INCHEON: "2800000000",
    Region.DAEJEON: "3000000000",
    Region.ULSAN: "3100000000",
    Region.SEJONG: "3600000000",
    Region.GYEONGGI: "4100000000",
    Region.CHUNGBUK: "4300000000",
    Region.CHUNGNAM: "4400000000",
    Region.GYEONGBUK: "4700000000",
    Region.GYEONGNAM: "4800000000",
    Region.JEJU: "5000000000",
    Region.GANGWON: "5100000000",
    Region.JEONBUK: "5200000000",
}

#: Korean display names, as published in the zone tree.
REGION_LABEL_KO: dict[Region, str] = {
    Region.SEOUL: "서울특별시",
    Region.GWANGJU_JEONNAM: "전남광주통합특별시",
    Region.BUSAN: "부산광역시",
    Region.DAEGU: "대구광역시",
    Region.INCHEON: "인천광역시",
    Region.DAEJEON: "대전광역시",
    Region.ULSAN: "울산광역시",
    Region.SEJONG: "세종특별자치시",
    Region.GYEONGGI: "경기도",
    Region.CHUNGBUK: "충청북도",
    Region.CHUNGNAM: "충청남도",
    Region.GYEONGBUK: "경상북도",
    Region.GYEONGNAM: "경상남도",
    Region.JEJU: "제주특별자치도",
    Region.GANGWON: "강원특별자치도",
    Region.JEONBUK: "전북특별자치도",
}

#: KMA publishes the index as an integer 0-3. Confirmed identical for oak, pine
#: and weeds in the V3 manual.
KMA_INDEX_TO_RISK_LEVEL: dict[str, RiskLevel] = {
    "0": RiskLevel.LOW,
    "1": RiskLevel.MODERATE,
    "2": RiskLevel.HIGH,
    "3": RiskLevel.VERY_HIGH,
}
