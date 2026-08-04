import type { PollenType, Region, RiskLevel } from "@pollen/contracts";

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
  forecast: {
    region: Region;
    pollenType: PollenType;
    modelVersion: string;
    days: Array<{
      date: string;
      riskLevel: RiskLevel;
      confidence: number | null;
    }>;
  };
}
