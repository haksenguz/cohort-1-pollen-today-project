import { z } from "zod";
import { RiskLevel } from "./graphql.js";

/**
 * Zod schemas for UNTRUSTED boundaries only — data arriving from outside the
 * system, where GraphQL offers no protection. See docs/adr/0004.
 *
 * Do not add schemas here for payloads the API itself defines. Those live in
 * the SDL, and a second definition would drift.
 */

/**
 * The KMA / data.go.kr pollen index response — HealthWthrIdxServiceV3.
 *
 * Verified against the live service on 2026-08-09 with a real key. Shape:
 *
 *   {"response":{"header":{"resultCode":"00","resultMsg":"NORMAL_SERVICE"},
 *     "body":{"dataType":"JSON","items":{"item":[
 *       {"code":"D08","areaNo":"1100000000","date":"2026080906",
 *        "today":"0","tomorrow":"0","dayaftertomorrow":"0",
 *        "twodaysaftertomorrow":""}]},
 *     "pageNo":1,"numOfRows":10,"totalCount":1}}}
 *
 * Three things this API does that make Zod worth having here:
 *
 * 1. Errors arrive as HTTP **200** with resultCode "99" and no `body` at all —
 *    e.g. "최근 1일 간의 자료만 제공합니다" or "해당지수자료 제공기간이 아닙니다".
 *    Checking the status code tells you nothing.
 * 2. Index values are STRINGS, not numbers: "0".."3".
 * 3. A slot that has not been published is an EMPTY STRING, not null and not
 *    absent. The 06:00 bulletin has no `twodaysaftertomorrow`; the 18:00
 *    bulletin has no `today`. Treating "" as 0 would publish a fake LOW.
 */

/** `""` when unpublished, otherwise "0".."3". */
export const KmaIndexValue = z.union([
  z.literal(""),
  z.enum(["0", "1", "2", "3"]),
]);
export type KmaIndexValue = z.infer<typeof KmaIndexValue>;

export const KmaPollenItem = z.object({
  /** Index code. D08 = weeds. */
  code: z.string(),
  areaNo: z.string(),
  /** Bulletin time, `YYYYMMDDHH` KST — when KMA published, not what it covers. */
  date: z.string().regex(/^\d{10}$/),
  today: KmaIndexValue,
  tomorrow: KmaIndexValue,
  dayaftertomorrow: KmaIndexValue,
  twodaysaftertomorrow: KmaIndexValue,
});
export type KmaPollenItem = z.infer<typeof KmaPollenItem>;

export const KmaResponse = z.object({
  response: z.object({
    header: z.object({
      resultCode: z.string(),
      resultMsg: z.string(),
    }),
    // Absent on every error, which is why it is optional rather than nullable.
    body: z
      .object({
        dataType: z.string().optional(),
        items: z.object({
          // data.go.kr collapses a single-element list to a bare object.
          item: z.union([KmaPollenItem, z.array(KmaPollenItem)]),
        }),
        pageNo: z.number().optional(),
        numOfRows: z.number().optional(),
        totalCount: z.number().optional(),
      })
      .optional(),
  }),
});
export type KmaResponse = z.infer<typeof KmaResponse>;

/** The only success code. Anything else carries its reason in resultMsg. */
export const KMA_OK = "00";

/** Normalises the single-object-or-array quirk into a list. */
export function kmaItems(parsed: KmaResponse): KmaPollenItem[] {
  const item = parsed.response.body?.items.item;
  if (!item) return [];
  return Array.isArray(item) ? item : [item];
}

/**
 * Which day each field describes, relative to the bulletin's own calendar date.
 * Used to turn one row into dated forecasts.
 */
export const KMA_DAY_OFFSETS = {
  today: 0,
  tomorrow: 1,
  dayaftertomorrow: 2,
  twodaysaftertomorrow: 3,
} as const satisfies Record<string, number>;

/**
 * The model artifact exported by ml/ and loaded at runtime (ADR 0002).
 * Validated on load so a malformed artifact fails at startup, not at 07:00 in
 * front of real subscribers.
 */
export const ModelArtifact = z.object({
  modelVersion: z.string().min(1),
  trainedAt: z.string().datetime(),
  features: z.array(z.string()).min(1),
  classes: z.array(z.nativeEnum(RiskLevel)).length(4),
  params: z.record(z.unknown()),
});
export type ModelArtifact = z.infer<typeof ModelArtifact>;

/** Environment configuration, parsed once at boot rather than read ad hoc. */
export const AppConfig = z.object({
  MONGODB_URI: z.string().min(1),
  PORT: z.coerce.number().int().positive().default(8000),
  TELEGRAM_BOT_TOKEN: z.string().optional(),
  TELEGRAM_OPS_CHAT_ID: z.string().optional(),
  /** JSON object mapping Region -> channel. See AlertChannels. */
  TELEGRAM_CHANNELS: z.string().optional(),
  KMA_API_KEY: z.string().optional(),
  ALERT_MIN_RISK_LEVEL: z.nativeEnum(RiskLevel).default(RiskLevel.HIGH),
});
export type AppConfig = z.infer<typeof AppConfig>;

// ALL_REGIONS lives in ./enums.ts, derived from REGION_AREA_NO so the list and
// the KMA area codes cannot fall out of step.
