import { Injectable, Logger } from "@nestjs/common";
import { InjectModel } from "@nestjs/mongoose";
import { Model } from "mongoose";
import { JobStatus } from "../../graphql.generated";
import type { NewAlert, PaginatedAlert, SystemStatus } from "./dto/alert.dto";
import type { AlertHistoryInput } from "./dto/alert-input.dto";
import { Alert, AlertDocument } from "./schemas/alert.schema";
import { JobRun, JobRunDocument } from "./schemas/job-run.schema";

/** Mongo's duplicate-key error code. */
const DUPLICATE_KEY = 11000;
const STALE_AFTER_MS = 26 * 60 * 60 * 1000;

@Injectable()
export class AlertsService {
  private readonly log = new Logger(AlertsService.name);

  constructor(
    @InjectModel(Alert.name) private readonly alerts: Model<AlertDocument>,
    @InjectModel(JobRun.name) private readonly jobRuns: Model<JobRunDocument>,
  ) {}

  /**
   * Records a delivery. Returns false when this exact alert was already sent —
   * the normal outcome of a re-run, not an error. See ADR 0003.
   *
   * Insert first, never check first: a read-then-write has a race window
   * between the two statements, and the unique index does not.
   */
  async recordDelivery(alert: NewAlert): Promise<boolean> {
    try {
      await this.alerts.create(alert);
      return true;
    } catch (err: unknown) {
      if (this.isDuplicateKey(err)) {
        this.log.log(
          `duplicate suppressed: ${alert.region}/${alert.pollenType}/${alert.targetDate}`,
        );
        return false;
      }
      throw err;
    }
  }

  private isDuplicateKey(err: unknown): boolean {
    return (
      typeof err === "object" &&
      err !== null &&
      "code" in err &&
      err.code === DUPLICATE_KEY
    );
  }

  async history({
    region,
    limit,
    offset,
  }: AlertHistoryInput): Promise<PaginatedAlert> {
    const filter = region ? { region } : {};

    const [docs, total] = await Promise.all([
      this.alerts
        .find(filter)
        .sort({ sentAt: -1 })
        .skip(offset)
        .limit(limit)
        .lean(),
      this.alerts.countDocuments(filter),
    ]);

    return {
      items: docs.map((d) => ({
        id: String(d._id),
        region: d.region,
        pollenType: d.pollenType,
        targetDate: d.targetDate,
        riskLevel: d.riskLevel,
        channel: d.channel,
        sentAt: d.sentAt,
        messageText: d.messageText,
      })),
      total,
      hasMore: offset + docs.length < total,
    };
  }

  async status(): Promise<SystemStatus> {
    const latest = await this.jobRuns.aggregate<JobRun>([
      { $sort: { startedAt: -1 } },
      { $group: { _id: "$jobName", doc: { $first: "$$ROOT" } } },
      { $replaceRoot: { newRoot: "$doc" } },
    ]);

    const now = Date.now();
    const stale = latest.some(
      (j) =>
        j.status !== JobStatus.SUCCESS ||
        now - j.startedAt.getTime() > STALE_AFTER_MS,
    );

    return { jobs: latest, stale };
  }
}
