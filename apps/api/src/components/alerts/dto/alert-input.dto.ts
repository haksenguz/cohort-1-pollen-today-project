import type { Region } from "@pollen/contracts";

/** Arguments of `Query.alertHistory`, mirroring src/schema/alerts.graphql. */
export interface AlertHistoryInput {
  region?: Region | null;
  limit: number;
  offset: number;
}
