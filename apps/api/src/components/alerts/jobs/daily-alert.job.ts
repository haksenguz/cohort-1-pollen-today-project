import { Injectable, Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { Cron } from "@nestjs/schedule";
import { PollenType, RiskLevel, riskAtLeast } from "@pollen/contracts";
import { ForecastService } from "../../forecast/forecast.service";
import { JobOutcome, JobRunner } from "../../jobs/job-runner.service";
import { kstDatePlus } from "../../../libs/kst";
import { AlertChannels } from "../alert-channels.service";
import { AlertsService } from "../alerts.service";
import { buildAlertMessage } from "../alert-message";
import { TelegramSender } from "../telegram/telegram.sender";

export const DAILY_ALERT_JOB = "daily-alert";

/**
 * The 07:00 KST morning alert. Slice C, Milestone 2.
 *
 * Posts about TOMORROW, not today: slide 4 defines success as "finds out that
 * tomorrow will be a high-pollen day, in time to do something about it".
 * Posting about the current day gives a person no time to act.
 * (Confirm with the mentor — this is the one product detail the deck and the
 * 07:00 timing do not pin down between them.)
 *
 * Every send is recorded through AlertsService, whose unique index makes a
 * re-run harmless. Re-running this job is therefore a safe operation, and
 * proving that live is what Milestone 2 grades.
 */
@Injectable()
export class DailyAlertJob {
  private readonly log = new Logger(DailyAlertJob.name);

  constructor(
    private readonly runner: JobRunner,
    private readonly forecast: ForecastService,
    private readonly alerts: AlertsService,
    private readonly channels: AlertChannels,
    private readonly telegram: TelegramSender,
    private readonly config: ConfigService,
  ) {}

  @Cron("0 7 * * *", { name: DAILY_ALERT_JOB, timeZone: "Asia/Seoul" })
  scheduled(): Promise<void> {
    return this.runner.run(DAILY_ALERT_JOB, () => this.execute());
  }

  /** Public so the job CLI and the tests can trigger a run without waiting for 07:00. */
  async execute(): Promise<JobOutcome> {
    const threshold = this.threshold();
    const targetDate = kstDatePlus(1);
    const pollenType = PollenType.WEEDS;
    let sent = 0;

    for (const region of this.channels.configuredRegions()) {
      const channel = this.channels.channelFor(region);
      if (!channel) continue;

      const forecast = this.forecast.threeDay(region, pollenType);
      const day = forecast.days.find((d) => d.date === targetDate);

      if (!day) {
        this.log.warn(`${region}: no forecast for ${targetDate}, skipped`);
        continue;
      }

      if (!riskAtLeast(day.riskLevel, threshold)) continue;

      const messageText = buildAlertMessage({
        region,
        pollenType,
        riskLevel: day.riskLevel,
        targetDate,
      });

      // Claim the slot BEFORE sending. If we sent first and then crashed, the
      // re-run would post a second time — the unique index only helps if the
      // write happens first.
      const claimed = await this.alerts.recordDelivery({
        region,
        pollenType,
        targetDate,
        riskLevel: day.riskLevel,
        channel,
        sentAt: new Date(),
        messageText,
      });

      if (!claimed) {
        this.log.log(`${region}: already sent for ${targetDate}`);
        continue;
      }

      await this.telegram.send(channel, messageText);
      sent += 1;
    }

    return { rowsAffected: sent };
  }

  private threshold(): RiskLevel {
    const raw =
      this.config.get<string>("ALERT_MIN_RISK_LEVEL") ?? RiskLevel.HIGH;
    const level = RiskLevel[raw as keyof typeof RiskLevel];

    if (!level) {
      throw new Error(`ALERT_MIN_RISK_LEVEL is not a RiskLevel: ${raw}`);
    }
    return level;
  }
}
