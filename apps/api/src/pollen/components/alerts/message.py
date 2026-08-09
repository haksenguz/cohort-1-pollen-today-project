"""The alert text that reaches a real person.

DRAFT — must be reviewed by Giyos for Korean (Week 2, Thu 20 Aug) and approved
by the mentor before it goes to a live channel.

Slide 15 forbids medical advice: we state the published index, point at KMA
guidance, and stop. No dosage, no product, no "you should take".
"""

from __future__ import annotations

from pollen.libs.enums import REGION_LABEL_KO, PollenType, Region, RiskLevel

RISK_LABEL_KO: dict[RiskLevel, str] = {
    RiskLevel.LOW: "낮음",
    RiskLevel.MODERATE: "보통",
    RiskLevel.HIGH: "높음",
    RiskLevel.VERY_HIGH: "매우 높음",
}

POLLEN_LABEL_KO: dict[PollenType, str] = {
    PollenType.OAK: "참나무",
    PollenType.PINE: "소나무",
    PollenType.WEEDS: "잡초류",
}

#: KMA's own public guidance page. Never our own health advice.
KMA_GUIDANCE_URL = "https://www.weather.go.kr/w/theme/daily-life/health-weather.do"


def build_alert_message(
    *,
    region: Region,
    pollen_type: PollenType,
    risk_level: RiskLevel,
    target_date: str,
) -> str:
    _, month, day = target_date.split("-")

    return "\n".join(
        [
            f"🌾 {REGION_LABEL_KO[region]} · {int(month)}월 {int(day)}일",
            "",
            f"{POLLEN_LABEL_KO[pollen_type]} 꽃가루농도위험지수: {RISK_LABEL_KO[risk_level]}",
            "",
            "기상청이 발표한 지수입니다. 자세한 생활 안내는 아래를 참고하세요.",
            KMA_GUIDANCE_URL,
            "",
            "※ 본 메시지는 의학적 조언이 아닙니다.",
        ]
    )
