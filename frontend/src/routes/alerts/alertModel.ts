/**
 * Pure helpers for the Alerts screen: filtering, collapsing runs of identical
 * alerts, day buckets and relative time. No React, no fetch, so the rules stay
 * easy to read and to test.
 */
import type { AlertResponse } from "../../api/types";

export type DayLabel = "Today" | "Yesterday" | "Earlier";

export interface AlertRun {
  /** Stable key: the id of the newest alert in the run. */
  key: string;
  /** Newest first. Always at least one item. */
  items: AlertResponse[];
  unread: number;
}

export interface DayGroup {
  label: DayLabel;
  runs: AlertRun[];
}

/** Alert kinds that describe the environment, so "Open Today" makes sense. */
const ENVIRONMENT_TYPES = new Set(["POLLEN", "AIR_QUALITY", "WEATHER"]);

const TYPE_LABEL: Record<string, string> = {
  POLLEN: "Pollen",
  AIR_QUALITY: "Air quality",
  WEATHER: "Weather",
  GENERAL: "General",
};

export function isEnvironmentAlert(alertType: string): boolean {
  return ENVIRONMENT_TYPES.has(alertType.toUpperCase());
}

export function typeLabel(alertType: string): string {
  const key = alertType.toUpperCase();
  if (TYPE_LABEL[key]) return TYPE_LABEL[key];
  const words = key.replace(/_/g, " ").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Filter keys: "all", "unread", or an alert_type such as "POLLEN". */
export function filterAlerts(alerts: AlertResponse[], filter: string): AlertResponse[] {
  if (filter === "all") return alerts;
  if (filter === "unread") return alerts.filter((a) => !a.is_read);
  return alerts.filter((a) => a.alert_type === filter);
}

/** The distinct alert types present, in the order they first appear. */
export function typesPresent(alerts: AlertResponse[]): string[] {
  const seen: string[] = [];
  for (const a of alerts) {
    if (!seen.includes(a.alert_type)) seen.push(a.alert_type);
  }
  return seen;
}

function sameAlert(a: AlertResponse, b: AlertResponse): boolean {
  return a.alert_type === b.alert_type && a.risk_level === b.risk_level && a.message === b.message;
}

/**
 * Collapses consecutive identical alerts (same type, level and text) into one
 * run. Input is newest first, so the runs stay newest first too.
 */
export function collapseRuns(alerts: AlertResponse[]): AlertRun[] {
  const runs: AlertRun[] = [];
  for (const a of alerts) {
    const last = runs[runs.length - 1];
    const unread = a.is_read ? 0 : 1;
    if (last && sameAlert(last.items[0], a)) {
      last.items.push(a);
      last.unread += unread;
    } else {
      runs.push({ key: String(a.id), items: [a], unread });
    }
  }
  return runs;
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function dayLabel(iso: string, now: Date): DayLabel {
  const day = startOfDay(new Date(iso));
  const today = startOfDay(now);
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime();
  if (day >= today) return "Today";
  if (day === yesterday) return "Yesterday";
  return "Earlier";
}

/** Buckets runs under Today, Yesterday and Earlier. Empty buckets are dropped. */
export function groupByDay(runs: AlertRun[], now: Date): DayGroup[] {
  const order: DayLabel[] = ["Today", "Yesterday", "Earlier"];
  const buckets = new Map<DayLabel, AlertRun[]>();
  for (const run of runs) {
    const label = dayLabel(run.items[0].created_at, now);
    buckets.set(label, [...(buckets.get(label) ?? []), run]);
  }
  return order.flatMap((label) => {
    const list = buckets.get(label);
    return list ? [{ label, runs: list }] : [];
  });
}

/** "just now", "12 min ago", "2 h ago", "3 d ago", then a short date. */
export function relativeAgo(iso: string, now: Date): string {
  const then = new Date(iso);
  const mins = Math.floor((now.getTime() - then.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} d ago`;
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
