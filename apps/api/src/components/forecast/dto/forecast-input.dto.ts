import type { PollenType, Region } from "../../../graphql.generated";

/** Arguments of `Query.forecast`, mirroring src/schema/forecast.graphql. */
export interface ForecastInput {
  region: Region;
  pollenType: PollenType;
}
