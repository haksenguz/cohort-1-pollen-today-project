/**
 * Overview rows for the settings screen.
 *
 * A row is a label plus the value you would see if you opened it. Every row
 * here opens a screen, so there is no row that quietly does nothing.
 *
 * The rows sit flat under a small grey label, the way ChatGPT groups its
 * settings: one hairline between rows, no card around them and no shadow.
 */
import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";

export type { SettingsScreenId } from "./settingsScreenIds";

function RowText({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">{value}</span>
    </span>
  );
}

/**
 * A labelled group of flat rows. The label is the only thing that separates
 * one area from the next, so it is small, grey and uppercase.
 */
export function SettingsGroup({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-1.5">
      <h2 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase">
        {title}
      </h2>
      <div className="flex flex-col divide-y divide-border">{children}</div>
    </section>
  );
}

/**
 * One row. The icon comes first, the title sits above the current value, and
 * the chevron says the row opens something.
 */
export function SettingsRow({
  label,
  value,
  icon,
  end,
  ariaExpanded,
  ariaControls,
  onSelect,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  /** Replaces the chevron, for a row that expands instead of navigating. */
  end?: ReactNode;
  ariaExpanded?: boolean;
  ariaControls?: string;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-expanded={ariaExpanded}
      aria-controls={ariaControls}
      className="flex min-h-11 w-full items-center gap-3 py-3 text-left transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </span>
      <RowText label={label} value={value} />
      {end ?? (
        <ChevronRight aria-hidden className="ml-auto size-4 shrink-0 text-muted-foreground" />
      )}
    </button>
  );
}
