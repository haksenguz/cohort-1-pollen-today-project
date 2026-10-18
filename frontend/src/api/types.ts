/**
 * Types mirror docs/API_CONTRACT.md. If the contract and the code disagree,
 * the code (backend/app/api/*.py + its Pydantic/SQLModel classes) wins —
 * update this file to match, not the other way round.
 */

// ---- Enums -----------------------------------------------------------

export type Allergen =
  // Tree
  | "BIRCH"
  | "OAK"
  | "ALDER"
  | "WILLOW"
  | "POPLAR"
  | "JAPANESE_CEDAR"
  | "PEACH"
  | "OLIVE"
  // Grass
  | "TIMOTHY"
  | "COCKSFOOT"
  | "ZOYSIA"
  | "BERMUDA_GRASS"
  | "SILVER_GRASS"
  | "WEEPING_GRASS"
  // Weed
  | "RAGWEED"
  | "MUGWORT"
  | "COCKLEBUR"
  | "BEGGAR_TICKS"
  | "LAMB_QUARTERS"
  | "DOCK"
  // Mould / fungal spore
  | "ALTERNARIA"
  | "CLADOSPORIUM"
  // Indoor
  | "HOUSE_DUST_MITE"
  | "COCKROACH"
  // Particulates
  | "PM25"
  | "PM10"
  // Legacy coarse buckets. Still accepted so existing rows keep scoring —
  // the backend resolves these by category, which is why BIRCH behaves the
  // same as TREE_POLLEN without a data migration.
  | "TREE_POLLEN"
  | "GRASS_POLLEN"
  | "WEED_POLLEN"
  | "DUST"
  | "MOLD"
  | "OTHER";

export type AllergySeverity = "MILD" | "MODERATE" | "SEVERE";

export type PollenLevel = "LOW" | "MODERATE" | "HIGH";

export type RiskLevel = "LOW" | "MODERATE" | "HIGH" | "EMERGENCY";

export type TriageLevel = "LOW" | "MODERATE" | "EMERGENCY";

// ---- Health ------------------------------------------------------------

export interface Health {
  status: string;
  service: string;
}

// ---- Auth ----------------------------------------------------------------

export interface RegisterRequest {
  email: string;
  password: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ---- Users -----------------------------------------------------------

export interface UserResponse {
  id: number;
  email: string;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
  updated_at: string;
}

export interface UserUpdateRequest {
  email?: string | null;
  password?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

// ---- Allergies -------------------------------------------------------

export interface AllergyResponse {
  id: number;
  allergen: Allergen;
  severity: AllergySeverity;
  created_at: string;
}

export interface AllergyCreateRequest {
  allergen: Allergen;
  severity: AllergySeverity;
}

// ---- Environment -------------------------------------------------------

/**
 * `GET /api/dev/llm` — the chat agent's server-wide credential.
 *
 * `key_hint` is the last few characters only. The key itself is never
 * returned in any form, not even masked-and-echoed.
 *
 * Only reachable when the backend runs with `DEV_SETTINGS_ENABLED=true`,
 * which is set solely in a gitignored local `.env`. Everywhere else the
 * route 404s and callers treat this as "the feature is not present".
 */
export interface DevLlmSettingsResponse {
  configured: boolean;
  key_hint: string | null;
  base_url: string;
  model: string;
}

/**
 * Body for `PUT /api/dev/llm`.
 *
 * An empty string means "leave the saved value unchanged" — never "clear it".
 * Clearing a credential is a `.env` edit, so there is no accidental way to
 * wipe a working key by submitting the form empty.
 */
export interface DevLlmSettingsUpdateRequest {
  api_key?: string;
  base_url?: string;
  model?: string;
}

/**
 * A `status` SSE event from `POST /api/chat`.
 *
 * `stage` names a step of the fixed agent pipeline ("extracting", "assessing").
 * It is NOT a tool call. Tool calls arrive as `tool` events, so nothing should
 * ever render a `status` event as "using tool X".
 */
export interface ChatStatusEvent {
  stage: string;
}

export interface EnvironmentResponse {
  latitude: number;
  longitude: number;
  pollen: {
    tree: PollenLevel | null;
    grass: PollenLevel | null;
    weed: PollenLevel | null;
  };
  air_quality: {
    pm25: number | null;
    pm10: number | null;
  };
  weather: {
    temperature: number | null;
    humidity: number | null;
    wind: number | null;
  };
  points: number;
  risk: RiskLevel;
  pollen_is_sample: boolean;
}

// ---- Triage --------------------------------------------------------------

export interface TriageRequest {
  symptoms?: string[];
  severity?: number | null;
  breathing_difficulty?: boolean;
  airway_swelling?: boolean;
}

export interface TriageResponse {
  level: TriageLevel;
  recommendation: string;
  reasons: string[];
  rule_version: string;
}

// ---- Chat (SSE) ------------------------------------------------------

export interface ChatRequest {
  message: string;
  conversation_id?: number | null;
}

export interface ChatResponse {
  message: string;
  conversation_id: number;
  symptoms: string[];
  severity: number | null;
  duration: string | null;
  possible_trigger: string | null;
  breathing_difficulty: boolean | null;
  airway_swelling: boolean | null;
  triage_level: TriageLevel | null;
  triage_reasons: string[];
  triage_rule_version: string | null;
  /**
   * Every tool the agent called this turn.
   *
   * Absent unless the backend sent an audit for this turn, so an absent key
   * means "this turn called no tools" and never has to be distinguished from an
   * empty array. See the additive rule in `client.ts`.
   */
  tool_calls?: ToolCallAudit[];
}

export interface ChatErrorEvent {
  detail: string;
}

// ---- Chat tools ---------------------------------------------------------
//
// Wire contract in docs/GOAL.md. ADR 0001 is the ceiling here: no tool type
// carries a triage level, severity or verdict, and no tool reports urgency.
// Those come from the deterministic engine in
// backend/app/services/triage.py and nowhere else.

/**
 * Where one tool call got to.
 *
 * `error` is also what a missing or unrecognised status degrades to. A call we
 * cannot read must never read as fine.
 */
export type ToolCallStatus = "running" | "done" | "error";

/**
 * One `tool` SSE event: the model chose a tool, and this is that call's
 * progress.
 *
 * `id` pairs a `running` event with its `done` or `error` event. An empty id
 * means the backend sent none, so pair events by `name` and order instead.
 *
 * `summary` is one short plain-English line, never a raw exception. It is null
 * when the backend sent none, or when the status was unreadable and the client
 * marked the call `error` itself.
 *
 * `result` is populated for tools that return data. Today that is
 * `find_nearby_care` only.
 *
 * `code` names WHY a call could not produce a result, in a small agreed set.
 * It exists so the three failures a user can act on never collapse into one
 * another: no location set is a five-second fix, a provider being offline is
 * not, and neither means "there are no clinics near you". An unrecognised code
 * is treated as a plain failure, never as success.
 */
export type ToolFailureCode = "no_location" | "provider_unavailable" | "no_hours_source";

export interface ToolCallEvent {
  id: string;
  name: string;
  status: ToolCallStatus;
  args?: Record<string, unknown> | null;
  summary?: string | null;
  result?: NearbyCareResult | null;
  code?: ToolFailureCode | string | null;
}

/**
 * One row of `ChatResponse.tool_calls`: the audit of what the agent did.
 *
 * `id` is optional. The backend lane added it so an audit row lines up with
 * its live `tool` event by id rather than by position; a response from a
 * backend without it still parses, so correlation degrades to order.
 */
export interface ToolCallAudit {
  id?: string | null;
  name: string;
  status: ToolCallStatus;
  summary?: string | null;
}

/** One clinic from `find_nearby_care`, already ranked by distance. */
export interface NearbyCareClinic {
  name: string;
  address: string | null;
  distance_m: number | null;
  phone: string | null;
  rank: number;
}

/**
 * What a clinic lookup returns for the chat to render.
 *
 * `provider_available` is the field that separates "searched and found none"
 * from "never searched", the same way it does on `HospitalNearbyResponse`. It
 * is optional because a backend that does not send it leaves the client unable
 * to claim either, which is the `unreadable` state rather than an empty list.
 */
export interface NearbyCareResult {
  clinics: NearbyCareClinic[];
  provider_available?: boolean | null;
}

// ---- Conversations --------------------------------------------------

export type ConversationMessageRole = "user" | "assistant";

/**
 * One row of `GET /api/conversations`.
 *
 * `title` is null until the backend generates one, so every caller needs a
 * fallback. `last_message` is null for a conversation that exists but has no
 * message rows yet. `message_count` counts message rows, not turns.
 */
export interface ConversationSummary {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  last_message: string | null;
  message_count: number;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
}

export interface ConversationMessage {
  id: number;
  role: ConversationMessageRole;
  content: string;
  triage_level: TriageLevel | null;
  triage_reasons: string[];
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  title: string | null;
  created_at: string;
  messages: ConversationMessage[];
}

// ---- Hospitals -------------------------------------------------------

export type HospitalSpecialty =
  | "ENT"
  | "ALLERGY"
  | "PULMONOLOGY"
  | "DERMATOLOGY"
  | "PEDIATRICS"
  | "EMERGENCY"
  | "GENERAL"
  | (string & {});

export interface HospitalResult {
  name: string;
  address: string | null;
  distance_m: number | null;
  specialty: string | null;
  category: string | null;
  phone: string | null;
  rank: number;
}

export interface HospitalNearbyResponse {
  latitude: number;
  longitude: number;
  specialty: string | null;
  provider_available: boolean;
  count: number;
  results: HospitalResult[];
}

export interface HospitalNearbyParams {
  lat: number;
  lon: number;
  specialty?: HospitalSpecialty;
  location_query?: string;
  radius_m?: number;
}

// ---- Notifications --------------------------------------------------

export interface AlertResponse {
  id: number;
  risk_level: RiskLevel;
  alert_type: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface PreferenceResponse {
  alert_pollen: boolean;
  alert_air_quality: boolean;
  alert_weather: boolean;
  min_risk_level: RiskLevel;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
}

export interface PreferenceUpdateRequest {
  alert_pollen?: boolean;
  alert_air_quality?: boolean;
  alert_weather?: boolean;
  min_risk_level?: RiskLevel;
  quiet_hours_start?: number | null;
  quiet_hours_end?: number | null;
}
