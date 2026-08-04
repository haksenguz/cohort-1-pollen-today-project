import { z } from "zod";
import { PollenType, Region, RiskLevel } from "./graphql.js";

/**
 * Zod schemas for UNTRUSTED boundaries only — data arriving from outside the
 * system, where GraphQL offers no protection. See docs/adr/0004.
 *
 * Do not add schemas here for payloads the API itself defines. Those live in
 * the SDL, and a second definition would drift.
 */

/**
 * The KMA / data.go.kr pollen index response.
 *
 * PLACEHOLDER — we have not seen a real response body yet, so the field names
 * below are a guess. See OPEN_QUESTIONS.md §2.2: obtaining one sample response
 * is the highest-value unblocking item on the project.
 */
export const KmaPollenRow = z.object({
  regionCode: z.string(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  pollenType: z.nativeEnum(PollenType),
  riskLevel: z.nativeEnum(RiskLevel),
});
export type KmaPollenRow = z.infer<typeof KmaPollenRow>;

export const KmaPollenResponse = z.object({
  rows: z.array(KmaPollenRow),
});
export type KmaPollenResponse = z.infer<typeof KmaPollenResponse>;

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
  KMA_API_KEY: z.string().optional(),
  ALERT_MIN_RISK_LEVEL: z.nativeEnum(RiskLevel).default(RiskLevel.HIGH),
});
export type AppConfig = z.infer<typeof AppConfig>;

/** Every region, as a value list. Derived — never a hand-written array. */
export const ALL_REGIONS = Object.values(Region);
