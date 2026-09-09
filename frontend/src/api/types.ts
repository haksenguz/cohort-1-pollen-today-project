/**
 * Types mirror docs/API_CONTRACT.md. If the contract and the code disagree,
 * the code (backend/app/api/*.py + its Pydantic/SQLModel classes) wins —
 * update this file to match, not the other way round.
 */

// ---- Enums -----------------------------------------------------------

export type Allergen =
  | "TREE_POLLEN"
  | "GRASS_POLLEN"
  | "WEED_POLLEN"
  | "PM25"
  | "PM10"
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
}

export interface ChatErrorEvent {
  detail: string;
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
  address: string;
  distance_m: number;
  specialty: string;
  category: string;
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
