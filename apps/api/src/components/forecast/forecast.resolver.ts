import { Args, Query, Resolver } from "@nestjs/graphql";
import type { Forecast } from "./dto/forecast.dto";
import type { ForecastInput } from "./dto/forecast-input.dto";
import { ForecastService } from "./forecast.service";

/**
 * Slice A — Forecast Engine. Owner: Jamshid.
 *
 * Thin by rule: args in, one service call, DTO out. All logic lives in the
 * service so it is testable without a GraphQL context.
 */
@Resolver("Forecast")
export class ForecastResolver {
  constructor(private readonly forecast: ForecastService) {}

  @Query("forecast")
  get(
    @Args("region") region: ForecastInput["region"],
    @Args("pollenType") pollenType: ForecastInput["pollenType"],
  ): Forecast {
    return this.forecast.threeDay(region, pollenType);
  }
}
