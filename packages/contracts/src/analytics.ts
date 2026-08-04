import { z } from "zod";
import { IsoDate, PollenType, Region } from "./enums.js";

/** Slice B — Season Analytics. Owner: Giyos (Release Owner). */

export const SeasonWindow = z.object({
  year: z.number().int().min(2000).max(2100),
  region: Region,
  pollenType: PollenType,
  startDate: IsoDate,
  endDate: IsoDate,
  lengthDays: z.number().int().nonnegative(),
});
export type SeasonWindow = z.infer<typeof SeasonWindow>;

export const SeasonTimingQuery = z.object({
  region: Region,
  pollenType: PollenType,
});
export type SeasonTimingQuery = z.infer<typeof SeasonTimingQuery>;

export const SeasonTimingResponse = z.object({
  region: Region,
  pollenType: PollenType,
  seasons: z.array(SeasonWindow),
  /** Slope in days per year. Positive means the season is lengthening. */
  lengthTrendDaysPerYear: z.number().nullable(),
});
export type SeasonTimingResponse = z.infer<typeof SeasonTimingResponse>;

export const RegionalLoadRow = z.object({
  region: Region,
  year: z.number().int(),
  highRiskDays: z.number().int().nonnegative(),
  veryHighRiskDays: z.number().int().nonnegative(),
});
export type RegionalLoadRow = z.infer<typeof RegionalLoadRow>;

export const RegionalLoadResponse = z.object({
  pollenType: PollenType,
  rows: z.array(RegionalLoadRow),
});
export type RegionalLoadResponse = z.infer<typeof RegionalLoadResponse>;
