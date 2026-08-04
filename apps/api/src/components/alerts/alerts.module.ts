import { Module } from "@nestjs/common";
import { MongooseModule } from "@nestjs/mongoose";
import { AlertsResolver } from "./alerts.resolver";
import { AlertsService } from "./alerts.service";
import { Alert, AlertSchema } from "./schemas/alert.schema";
import { JobRun, JobRunSchema } from "./schemas/job-run.schema";

@Module({
  imports: [
    MongooseModule.forFeature([
      { name: Alert.name, schema: AlertSchema },
      { name: JobRun.name, schema: JobRunSchema },
    ]),
  ],
  providers: [AlertsResolver, AlertsService],
  exports: [AlertsService],
})
export class AlertsModule {}
