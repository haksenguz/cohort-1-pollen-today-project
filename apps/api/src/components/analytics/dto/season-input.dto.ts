import type { PollenType, Region } from "@pollen/contracts";

/** Arguments of `Query.seasonTiming`, mirroring src/schema/analytics.graphql. */
export interface SeasonTimingInput {
  region: Region;
  pollenType: PollenType;
}
