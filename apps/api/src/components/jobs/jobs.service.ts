import { Injectable } from "@nestjs/common";
import { JobStatus } from "@pollen/contracts";
import { Model } from "mongoose";
import { InjectModel } from "@nestjs/mongoose";
import type { SystemStatus } from "./dto/job-run.dto";
import { JobRun, JobRunDocument } from "./schemas/job-run.schema";

/**
 * A daily job that last succeeded more than 26 hours ago has missed a run.
 * 26 rather than 24 so a late start or a slow run does not raise a false alarm.
 */
const STALE_AFTER_MS = 26 * 60 * 60 * 1000;

@Injectable()
export class JobsService {
  constructor(
    @InjectModel(JobRun.name) private readonly runs: Model<JobRunDocument>,
  ) {}

  /** Newest run per job name, plus whether anything has gone stale. */
  async status(now: Date = new Date()): Promise<SystemStatus> {
    const latest = await this.runs.aggregate<JobRunDocument>([
      { $sort: { startedAt: -1 } },
      { $group: { _id: "$jobName", doc: { $first: "$$ROOT" } } },
      { $replaceRoot: { newRoot: "$doc" } },
      { $sort: { jobName: 1 } },
    ]);

    const stale = latest.some(
      (j) =>
        j.status !== JobStatus.SUCCESS ||
        now.getTime() - j.startedAt.getTime() > STALE_AFTER_MS,
    );

    return {
      jobs: latest.map((j) => ({
        jobName: j.jobName,
        startedAt: j.startedAt,
        finishedAt: j.finishedAt,
        status: j.status,
        rowsAffected: j.rowsAffected,
        error: j.error,
      })),
      stale,
    };
  }
}
