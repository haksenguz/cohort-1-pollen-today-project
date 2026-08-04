/**
 * Every calendar date in this system is a KST date. The alert job runs at
 * 07:00 KST and forecasts are "tomorrow" in Seoul, not in UTC — so date maths
 * must never go through the host timezone.
 */
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

export function kstToday(now: Date = new Date()): string {
  return new Date(now.getTime() + KST_OFFSET_MS).toISOString().slice(0, 10);
}

export function kstDatePlus(days: number, now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + KST_OFFSET_MS + days * 86_400_000);
  return shifted.toISOString().slice(0, 10);
}
