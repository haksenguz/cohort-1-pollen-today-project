/** Slice C read types. Source of truth: src/schema/alerts.graphql. */
export type {
  Alert,
  JobRun,
  PaginatedAlert,
  SystemStatus,
} from "../../../graphql.generated";

/** What the alert job hands the service. The id is assigned by Mongo. */
export type NewAlert = Omit<
  import("../../../graphql.generated").Alert,
  "id" | "sentAt"
> & {
  sentAt: Date;
};
