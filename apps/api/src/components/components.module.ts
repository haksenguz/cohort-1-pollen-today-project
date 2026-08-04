import { Module } from "@nestjs/common";
import { AlertsModule } from "./alerts/alerts.module";
import { AnalyticsModule } from "./analytics/analytics.module";
import { ForecastModule } from "./forecast/forecast.module";

const COMPONENTS = [ForecastModule, AnalyticsModule, AlertsModule];

/**
 * The single aggregate of every feature module.
 *
 * AppModule imports this and nothing else from the feature side, so adding a
 * component means touching one line here rather than editing AppModule —
 * which is the file most likely to cause a merge conflict between three people.
 */
@Module({
  imports: COMPONENTS,
  exports: COMPONENTS,
})
export class ComponentsModule {}
