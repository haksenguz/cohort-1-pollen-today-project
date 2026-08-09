import { Injectable, Logger } from "@nestjs/common";
import { InjectModel } from "@nestjs/mongoose";
import { JobStatus } from "@pollen/contracts";
import { Model } from "mongoose";
import { OpsNotifier } from "./ops-notifier.service";
import { JobRun, JobRunDocument } from "./schemas/job-run.schema";

/** What a job reports back. `rowsAffected` feeds the status page. */
export interface JobOutcome {
  rowsAffected: number;
}

export type JobBody = () => Promise<JobOutcome>;

/**
 * Wraps every scheduled job with instrumentation.
 *
 * A job that is not recorded is a job nobody can prove ran. Each execution
 * writes one JobRun document: RUNNING on entry, then SUCCESS or FAILED with the
 * row count or the error. The status page reads the newest row per job name,
 * and a job that has not succeeded in 26 hours shows red.
 *
 * Jobs are deliberately NOT allowed to throw past this boundary — a scheduler
 * that dies on an unhandled rejection stops running every other job too.
 */
@Injectable()
export class JobRunner {
  private readonly log = new Logger(JobRunner.name);

  constructor(
    @InjectModel(JobRun.name) private readonly runs: Model<JobRunDocument>,
    private readonly ops: OpsNotifier,
  ) {}

  async run(jobName: string, body: JobBody): Promise<void> {
    const startedAt = new Date();
    const run = await this.runs.create({
      jobName,
      startedAt,
      status: JobStatus.RUNNING,
    });

    try {
      const { rowsAffected } = await body();

      await this.runs.updateOne(
        { _id: run._id },
        { finishedAt: new Date(), status: JobStatus.SUCCESS, rowsAffected },
      );
      this.log.log(`${jobName}: ok, ${rowsAffected} rows`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);

      await this.runs.updateOne(
        { _id: run._id },
        { finishedAt: new Date(), status: JobStatus.FAILED, error: message },
      );
      this.log.error(`${jobName}: failed — ${message}`, this.stackOf(err));

      // Failing to tell anyone is worse than the failure. Never let the
      // notifier's own error mask the job's.
      await this.ops.jobFailed(jobName, message).catch((notifyErr: unknown) => {
        this.log.error(`ops notify failed: ${String(notifyErr)}`);
      });
    }
  }

  private stackOf(err: unknown): string | undefined {
    return err instanceof Error ? err.stack : undefined;
  }
}
