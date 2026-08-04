import { z } from "zod";
import { IsoDate, PollenType, Region, RiskLevel } from "./enums.js";

/** Slice C — Alerts & Delivery. Owner: Ismoiljon (Tech Lead). */

export const AlertRecord = z.object({
  id: z.string().uuid(),
  region: Region,
  pollenType: PollenType,
  /** The day the alert is *about*, not the day it was sent. */
  targetDate: IsoDate,
  riskLevel: RiskLevel,
  channel: z.string().min(1),
  sentAt: z.string().datetime(),
  messageText: z.string(),
});
export type AlertRecord = z.infer<typeof AlertRecord>;

export const AlertHistoryQuery = z.object({
  region: Region.optional(),
  limit: z.coerce.number().int().min(1).max(200).default(50),
});
export type AlertHistoryQuery = z.infer<typeof AlertHistoryQuery>;

export const AlertHistoryResponse = z.object({
  alerts: z.array(AlertRecord),
});
export type AlertHistoryResponse = z.infer<typeof AlertHistoryResponse>;

/**
 * The idempotency key. A UNIQUE constraint on
 * (channel, region, pollen_type, target_date) is what makes re-running the
 * 07:00 job harmless. The guarantee lives in the database, not in app logic.
 */
export const AlertIdempotencyKey = z.object({
  channel: z.string().min(1),
  region: Region,
  pollenType: PollenType,
  targetDate: IsoDate,
});
export type AlertIdempotencyKey = z.infer<typeof AlertIdempotencyKey>;

/** Job-run instrumentation — feeds the status page. */
export const JobRunStatus = z.enum(["SUCCESS", "FAILED", "RUNNING"]);
export type JobRunStatus = z.infer<typeof JobRunStatus>;

export const JobRun = z.object({
  jobName: z.string(),
  startedAt: z.string().datetime(),
  finishedAt: z.string().datetime().nullable(),
  status: JobRunStatus,
  rowsAffected: z.number().int().nonnegative().nullable(),
  error: z.string().nullable(),
});
export type JobRun = z.infer<typeof JobRun>;

export const StatusResponse = z.object({
  jobs: z.array(JobRun),
  /** True when any job has not succeeded in over 26 hours. */
  stale: z.boolean(),
});
export type StatusResponse = z.infer<typeof StatusResponse>;
