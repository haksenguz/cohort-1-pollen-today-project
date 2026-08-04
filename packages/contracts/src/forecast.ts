import { z } from "zod";
import { IsoDate, PollenType, Region, RiskLevel } from "./enums.js";

/** Slice A — Forecast Engine. Owner: Jamshid (Contract Owner). */

export const ForecastDay = z.object({
  date: IsoDate,
  riskLevel: RiskLevel,
  /** Model confidence for the predicted class, 0–1. Null for the baseline. */
  confidence: z.number().min(0).max(1).nullable(),
});
export type ForecastDay = z.infer<typeof ForecastDay>;

export const ForecastQuery = z.object({
  region: Region,
  pollenType: PollenType.default("WEEDS"),
});
export type ForecastQuery = z.infer<typeof ForecastQuery>;

export const ForecastResponse = z.object({
  region: Region,
  pollenType: PollenType,
  /** Exactly three days ahead. Slide 15: beyond three days is out of scope. */
  days: z.array(ForecastDay).length(3),
  /** e.g. "baseline-persistence-v1" or "gbm-v3". Required — never omit. */
  modelVersion: z.string().min(1),
  generatedAt: z.string().datetime(),
});
export type ForecastResponse = z.infer<typeof ForecastResponse>;
