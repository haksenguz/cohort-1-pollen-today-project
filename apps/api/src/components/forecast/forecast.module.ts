import { Module } from "@nestjs/common";
import { ForecastResolver } from "./forecast.resolver";
import { ForecastService } from "./forecast.service";

@Module({
  providers: [ForecastResolver, ForecastService],
  exports: [ForecastService],
})
export class ForecastModule {}
