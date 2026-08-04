import type { Alert } from "@pollen/contracts";

/** Slice C read types. Source of truth: src/schema/alerts.graphql. */
export type {
  Alert,
  JobRun,
  PaginatedAlert,
  SystemStatus,
} from "@pollen/contracts";

/** What the alert job hands the service. The id is assigned by Mongo. */
export type NewAlert = Omit<Alert, "id" | "sentAt"> & { sentAt: Date };
