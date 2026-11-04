/**
 * Text size preference — bugs.md F4, WCAG 2.2 SC 1.4.4 Resize Text (AA).
 *
 * The control scales the root font size rather than a wrapper: Tailwind's
 * whole utility scale is rem-based, so moving the root reflows the app and
 * every rem length follows it. `transform: scale()` on a wrapper would leave
 * the layout at its original size and paint it larger, which is what pushes
 * content off screen instead of reflowing it. Nothing here touches the viewport
 * meta or the browser's own zoom, so ctrl-plus and pinch keep working and a
 * reader can reach 200% that way too.
 *
 * Base: the browser's own default root size (16px on every current browser,
 * and the size the rem scale is authored against). Each step is a percentage of
 * that base rather than a pixel count, so a reader who has already raised their
 * browser's default text size keeps that on top of this one.
 *
 * Nothing here parses or computes a number out of the stored string: the value
 * is matched against the id table, and the size handed to the DOM is a literal
 * from that same table. A missing or unreadable value therefore cannot reach
 * the document as NaN or 0px. It lands on the default step by name, checked
 * first — a table lookup miss that quietly substitutes a neighbouring step is
 * the `RISK_CLASS[level] ?? "low"` shape in utils/format.ts that this project
 * has a bug entry about.
 */
import { useCallback, useState } from "react";

import "./textSize.css";

export const TEXT_SIZE_STORAGE_KEY = "allergy_companion_text_size";

const TEXT_SIZE_IDS = ["normal", "large", "larger", "largest"] as const;

export type TextSizeId = (typeof TEXT_SIZE_IDS)[number];

export interface TextSizeStep {
  readonly id: TextSizeId;
  readonly label: string;
  /** Percentage of the browser's default root font size. */
  readonly percent: number;
}

export const DEFAULT_TEXT_SIZE: TextSizeStep = {
  id: "normal",
  label: "Normal",
  percent: 100,
};

const STEPS: Record<TextSizeId, TextSizeStep> = {
  normal: DEFAULT_TEXT_SIZE,
  large: { id: "large", label: "Large", percent: 125 },
  larger: { id: "larger", label: "Larger", percent: 150 },
  // 200% is the size SC 1.4.4 asks for, so it is a step of its own rather than
  // something only browser zoom can reach.
  largest: { id: "largest", label: "Largest", percent: 200 },
};

export const TEXT_SIZE_STEPS: readonly TextSizeStep[] = TEXT_SIZE_IDS.map(
  (id) => STEPS[id],
);

export function isTextSizeId(value: unknown): value is TextSizeId {
  return typeof value === "string" && (TEXT_SIZE_IDS as readonly string[]).includes(value);
}

/**
 * The step a stored value names, or the default when it names none. Matching is
 * on the id and not on the record, so `"toString"` and `"0"` are misses like
 * any other junk rather than an inherited property.
 */
export function resolveTextSize(stored: string | null | undefined): TextSizeStep {
  if (typeof stored !== "string") return DEFAULT_TEXT_SIZE;
  const id = stored.trim();
  return isTextSizeId(id) ? STEPS[id] : DEFAULT_TEXT_SIZE;
}

/** What goes on <html>. A literal out of the table, never arithmetic. */
export function rootFontSizeFor(step: TextSizeStep): string {
  return `${step.percent}%`;
}

function safeStorage(): Storage | null {
  // Private browsing and blocked storage throw on the property access itself,
  // not only on the call. Same trap as auth/token.ts.
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

export function readTextSize(): TextSizeStep {
  try {
    return resolveTextSize(safeStorage()?.getItem(TEXT_SIZE_STORAGE_KEY));
  } catch {
    return DEFAULT_TEXT_SIZE;
  }
}

export function storeTextSize(step: TextSizeStep): void {
  try {
    safeStorage()?.setItem(TEXT_SIZE_STORAGE_KEY, step.id);
  } catch {
    // Storage refused it. The size still applies for this session; only the
    // choice will not survive a reload.
  }
}

export function applyTextSize(step: TextSizeStep): void {
  if (typeof document === "undefined") return;
  document.documentElement.style.fontSize = rootFontSizeFor(step);
}

export function useTextSize(): {
  step: TextSizeStep;
  setStep: (next: TextSizeStep) => void;
} {
  const [step, setCurrent] = useState<TextSizeStep>(readTextSize);

  const setStep = useCallback((next: TextSizeStep) => {
    setCurrent(next);
    applyTextSize(next);
    storeTextSize(next);
  }, []);

  return { step, setStep };
}

// Applied at module load rather than only when the settings screen mounts: the
// app entry imports the settings route, so this runs before the first paint and
// a reload opens at the size that was chosen.
applyTextSize(readTextSize());