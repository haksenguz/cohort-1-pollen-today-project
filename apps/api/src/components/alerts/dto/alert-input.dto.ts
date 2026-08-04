import type { Region } from "../../../graphql.generated";

/** Arguments of `Query.alertHistory`, mirroring src/schema/alerts.graphql. */
export interface AlertHistoryInput {
  region?: Region | null;
  limit: number;
  offset: number;
}
