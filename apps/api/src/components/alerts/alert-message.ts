import {
  PollenType,
  REGION_LABEL_KO,
  Region,
  RiskLevel,
} from "@pollen/contracts";

/**
 * The alert text that reaches a real person.
 *
 * DRAFT — must be reviewed by Giyos for Korean (Week 2, Thu 20 Aug) and
 * approved by the mentor before it goes to a live channel.
 *
 * Slide 15 forbids medical advice: we state the published index, point at KMA
 * guidance, and stop. No dosage, no product, no "you should take".
 */

const RISK_LABEL_KO: Record<RiskLevel, string> = {
  [RiskLevel.LOW]: "낮음",
  [RiskLevel.MODERATE]: "보통",
  [RiskLevel.HIGH]: "높음",
  [RiskLevel.VERY_HIGH]: "매우 높음",
};

const POLLEN_LABEL_KO: Record<PollenType, string> = {
  [PollenType.OAK]: "참나무",
  [PollenType.PINE]: "소나무",
  [PollenType.WEEDS]: "잡초류",
};

/** KMA's own public guidance page. Never our own health advice. */
const KMA_GUIDANCE_URL =
  "https://www.weather.go.kr/w/theme/daily-life/health-weather.do";

export interface AlertMessageInput {
  region: Region;
  pollenType: PollenType;
  riskLevel: RiskLevel;
  /** The day the forecast is about, `YYYY-MM-DD` KST. */
  targetDate: string;
}

export function buildAlertMessage({
  region,
  pollenType,
  riskLevel,
  targetDate,
}: AlertMessageInput): string {
  const [, month, day] = targetDate.split("-");

  return [
    `🌾 ${REGION_LABEL_KO[region]} · ${month}월 ${day}일`,
    "",
    `${POLLEN_LABEL_KO[pollenType]} 꽃가루농도위험지수: ${RISK_LABEL_KO[riskLevel]}`,
    "",
    "기상청이 발표한 지수입니다. 자세한 생활 안내는 아래를 참고하세요.",
    KMA_GUIDANCE_URL,
    "",
    "※ 본 메시지는 의학적 조언이 아닙니다.",
  ].join("\n");
}
