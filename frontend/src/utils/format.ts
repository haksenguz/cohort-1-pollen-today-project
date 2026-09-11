/**
 * Pure display formatters shared by the Today and Alerts screens.
 * No React, no fetch, no DOM. Kept small so unit tests stay fast.
 */
import type { PollenLevel, RiskLevel } from "../api/types";

const DASH = "—";

const RISK_LABEL: Record<RiskLevel, string> = {
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  EMERGENCY: "Emergency",
};

const RISK_CLASS: Record<RiskLevel, string> = {
  LOW: "low",
  MODERATE: "moderate",
  HIGH: "high",
  EMERGENCY: "emergency",
};

const POLLEN_LABEL: Record<PollenLevel, string> = {
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
};

export function formatRisk(level: RiskLevel): string {
  return RISK_LABEL[level] ?? level;
}

export function riskClass(level: RiskLevel): string {
  return RISK_CLASS[level] ?? "low";
}

export function formatPollen(level: PollenLevel | null): string {
  if (level === null || level === undefined) return DASH;
  return POLLEN_LABEL[level] ?? level;
}

export function formatDistance(meters: number | null): string {
  if (meters === null || meters === undefined) return DASH;
  if (meters < 1000) return `${meters} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

export function formatPoints(points: number): string {
  return String(points);
}

/**
 * Compact "5 min ago" / "3 h ago" / "2 d ago" stamp for the alerts list.
 * Returns a dash if the input is not a parseable ISO timestamp — better
 * a dash than "Invalid Date" in a user's notifications.
 */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return DASH;
  const diffMs = now.getTime() - then.getTime();
  if (diffMs < 60_000) return "just now";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}
