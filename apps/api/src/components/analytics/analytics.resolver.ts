import { Args, Query, Resolver } from "@nestjs/graphql";
import { AnalyticsService } from "./analytics.service";
import type { SeasonTiming } from "./dto/season.dto";
import type { SeasonTimingInput } from "./dto/season-input.dto";

/**
 * Slice B — Season Analytics. Owner: Giyos.
 * Giyos replaces the service body; the SDL and this resolver stay frozen.
 */
@Resolver("SeasonTiming")
export class AnalyticsResolver {
  constructor(private readonly analytics: AnalyticsService) {}

  @Query("seasonTiming")
  seasonTiming(
    @Args("region") region: SeasonTimingInput["region"],
    @Args("pollenType") pollenType: SeasonTimingInput["pollenType"],
  ): SeasonTiming {
    return this.analytics.seasonTiming(region, pollenType);
  }
}
