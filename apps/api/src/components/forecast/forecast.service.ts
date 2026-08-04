import { Injectable } from "@nestjs/common";
import { PollenType, Region, RiskLevel } from "../../graphql.generated";
import { kstDatePlus } from "../../libs/kst";
import type { Forecast } from "./dto/forecast.dto";

@Injectable()
export class ForecastService {
  /**
   * Persistence baseline placeholder: MODERATE for three days.
   *
   * Deliberately not a real prediction. It exists so Slice C can build and test
   * the alert job against a live query before Slice A is written. Jamshid
   * replaces this with the real baseline (tomorrow equals today), then the
   * trained model. The SDL does not change when he does.
   */
  threeDay(region: Region, pollenType: PollenType): Forecast {
    return {
      region,
      pollenType,
      days: [1, 2, 3].map((offset) => ({
        date: kstDatePlus(offset),
        riskLevel: RiskLevel.MODERATE,
        confidence: null,
      })),
      modelVersion: "stub-v0",
      generatedAt: new Date(),
    };
  }
}
