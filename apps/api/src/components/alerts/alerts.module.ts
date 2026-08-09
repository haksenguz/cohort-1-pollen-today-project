import { Module } from "@nestjs/common";
import { MongooseModule } from "@nestjs/mongoose";
import { ForecastModule } from "../forecast/forecast.module";
import { JobsModule } from "../jobs/jobs.module";
import { AlertChannels } from "./alert-channels.service";
import { AlertsResolver } from "./alerts.resolver";
import { AlertsService } from "./alerts.service";
import { DailyAlertJob } from "./jobs/daily-alert.job";
import { Alert, AlertSchema } from "./schemas/alert.schema";

@Module({
  imports: [
    MongooseModule.forFeature([{ name: Alert.name, schema: AlertSchema }]),
    // The alert job reads the forecast and records its runs.
    ForecastModule,
    JobsModule,
  ],
  providers: [AlertsResolver, AlertsService, AlertChannels, DailyAlertJob],
  exports: [AlertsService],
})
export class AlertsModule {}
