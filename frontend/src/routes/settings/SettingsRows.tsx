/**
 * Overview rows for the settings screen.
 *
 * A row is a label plus the value you would see if you opened it. Rows with a
 * screen behind them are buttons. Rows whose screen is not built yet are plain
 * text, so nothing on the overview looks like a control that quietly does
 * nothing.
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

export function SettingsCard({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col divide-y divide-border overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
      {children}
    </div>
  );
}

export function SettingsGroup({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase">
        {title}
      </h2>
      <SettingsCard>{children}</SettingsCard>
    </section>
  );
}

export function SettingsRow({
  label,
  value,
  onSelect,
}: {
  label: string;
  value: string;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="flex min-h-11 w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
    >
      <RowText label={label} value={value} />
      <ChevronRight aria-hidden className="ml-auto size-4 shrink-0 text-muted-foreground" />
    </button>
  );
}

export function ComingSoonRow({ label }: { label: string }) {
  return (
    <div className="flex min-h-11 w-full items-center gap-3 px-4 py-3">
      <RowText label={label} value="Not built yet" />
    </div>
  );
}

export function ComingSoonGroup({
  title,
  rows,
}: {
  title: string;
  rows: readonly string[];
}) {
  return (
    <SettingsGroup title={title}>
      {rows.map((label) => (
        <ComingSoonRow key={label} label={label} />
      ))}
    </SettingsGroup>
  );
}