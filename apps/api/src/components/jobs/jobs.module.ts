import { Module } from "@nestjs/common";
import { MongooseModule } from "@nestjs/mongoose";
import { TelegramSender } from "../alerts/telegram/telegram.sender";
import { JobRunner } from "./job-runner.service";
import { JobsResolver } from "./jobs.resolver";
import { JobsService } from "./jobs.service";
import { OpsNotifier } from "./ops-notifier.service";
import { JobRun, JobRunSchema } from "./schemas/job-run.schema";

/**
 * Job instrumentation, shared by every slice that schedules work.
 *
 * Exports JobRunner so a slice can wrap its own job without re-implementing
 * run recording or failure notification.
 */
@Module({
  imports: [
    MongooseModule.forFeature([{ name: JobRun.name, schema: JobRunSchema }]),
  ],
  providers: [
    JobsResolver,
    JobsService,
    JobRunner,
    OpsNotifier,
    TelegramSender,
  ],
  exports: [JobRunner, TelegramSender],
})
export class JobsModule {}
