import type { PollenType, Region } from "../../../graphql.generated";

/** Arguments of `Query.seasonTiming`, mirroring src/schema/analytics.graphql. */
export interface SeasonTimingInput {
  region: Region;
  pollenType: PollenType;
}
