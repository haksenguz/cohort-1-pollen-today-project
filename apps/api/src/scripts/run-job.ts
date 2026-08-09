import "reflect-metadata";
import { Logger } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "../app.module";
import {
  DAILY_ALERT_JOB,
  DailyAlertJob,
} from "../components/alerts/jobs/daily-alert.job";
import { JobRunner } from "../components/jobs/job-runner.service";

/**
 * Job CLI — run a scheduled job now, without waiting for its cron.
 *
 *   node dist/scripts/run-job.js daily-alert
 *
 * Goes through JobRunner exactly as the scheduler does, so a manual run is
 * recorded and instrumented identically. That matters for Milestone 2: proving
 * idempotency means re-running the real job, not a special test path.
 */
async function main() {
  const [, , jobName] = process.argv;

  if (!jobName) {
    process.stderr.write(
      `usage: run-job <job>\navailable: ${DAILY_ALERT_JOB}\n`,
    );
    process.exit(2);
  }

  const app = await NestFactory.createApplicationContext(AppModule);

  try {
    switch (jobName) {
      case DAILY_ALERT_JOB: {
        const job = app.get(DailyAlertJob);
        await app.get(JobRunner).run(DAILY_ALERT_JOB, () => job.execute());
        break;
      }
      default:
        process.stderr.write(`unknown job: ${jobName}\n`);
        process.exitCode = 2;
    }
  } finally {
    await app.close();
    Logger.flush();
  }
}

void main();
