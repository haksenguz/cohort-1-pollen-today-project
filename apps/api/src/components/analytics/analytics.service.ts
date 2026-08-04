import { Injectable } from "@nestjs/common";
import type { PollenType, Region } from "../../graphql.generated";
import type { SeasonTiming } from "./dto/season.dto";

@Injectable()
export class AnalyticsService {
  /** STUB — blocked on historical KMA data. See OPEN_QUESTIONS.md §2.3. */
  seasonTiming(region: Region, pollenType: PollenType): SeasonTiming {
    return {
      region,
      pollenType,
      seasons: [],
      lengthTrendDaysPerYear: null,
    };
  }
}
