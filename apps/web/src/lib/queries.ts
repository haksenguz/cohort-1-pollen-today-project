import type { Forecast, PollenType, Region } from "@pollen/contracts";

/**
 * Query documents and their variable types.
 *
 * Result types come from `@pollen/contracts`, which is generated from the SDL.
 * Never hand-write a response interface here — if a field is missing from the
 * generated type, the SDL is what needs changing.
 */

export const FORECAST_QUERY = /* GraphQL */ `
  query Forecast($region: Region!, $pollenType: PollenType!) {
    forecast(region: $region, pollenType: $pollenType) {
      region
      pollenType
      modelVersion
      days {
        date
        riskLevel
        confidence
      }
    }
  }
`;

export interface ForecastVars extends Record<string, unknown> {
  region: Region;
  pollenType: PollenType;
}

export interface ForecastData {
  forecast: Forecast;
}
