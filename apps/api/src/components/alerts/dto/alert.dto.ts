import type { Alert } from "@pollen/contracts";

/** Slice C read types. Source of truth: src/schema/alerts.graphql. */
export type { Alert, PaginatedAlert } from "@pollen/contracts";

/**
 * What the alert job hands the service. Mongo assigns the id, and `sentAt` is a
 * real Date here rather than the serialised string the schema exposes.
 */
export type NewAlert = Omit<Alert, "id" | "sentAt"> & { sentAt: Date };
