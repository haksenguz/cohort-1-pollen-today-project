import { Args, Query, Resolver } from "@nestjs/graphql";
import { AlertsService } from "./alerts.service";
import type { PaginatedAlert } from "./dto/alert.dto";
import type { AlertHistoryInput } from "./dto/alert-input.dto";

/**
 * Slice C — Alerts & Delivery. Owner: Ismoiljon.
 * Backs the public alert-history page.
 */
@Resolver("Alert")
export class AlertsResolver {
  constructor(private readonly alerts: AlertsService) {}

  @Query("alertHistory")
  history(
    @Args("region") region: AlertHistoryInput["region"],
    @Args("limit") limit: number,
    @Args("offset") offset: number,
  ): Promise<PaginatedAlert> {
    return this.alerts.history({ region, limit, offset });
  }
}
