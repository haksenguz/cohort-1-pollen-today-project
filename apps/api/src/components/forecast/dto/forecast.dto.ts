/**
 * Slice A read types.
 *
 * Re-exported from @pollen/contracts so components import from their own `dto/`
 * folder rather than reaching across the package. The SDL in
 * src/schema/forecast.graphql remains the source of truth.
 */
export type { Forecast, ForecastDay } from "@pollen/contracts";
