/**
 * Overview rows for the settings screen.
 *
 * A row is an icon tile, a title over the current value, and a chevron. Every
 * row here opens a screen, so there is no row that quietly does nothing.
 *
 * Rows sit inside an inset rounded card. The card is the unit; the label above
 * it names the area. Hairlines separate rows inside one card.
 */
import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";

export type { SettingsScreenId } from "./settingsScreenIds";

/** `danger` tints the icon tile red. Used for rows that delete things. */
export type SettingsRowTone = "default" | "danger";

/**
 * A labelled group. The label sits 8px above the card, and the card holds the
 * rows. The label is the heading, so screen readers and the tests can find it.
 */
export function SettingsGroup({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="settings-group">
      <h2 className="settings-group-label">{title}</h2>
      <div className="settings-card">{children}</div>
    </section>
  );
}

/**
 * One row. The icon tile comes first, the title sits above the current value,
 * and the chevron says the row opens something.
 */
export function SettingsRow({
  label,
  value,
  icon,
  tone = "default",
  end,
  ariaExpanded,
  ariaControls,
  onSelect,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  tone?: SettingsRowTone;
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
      className="settings-row"
    >
      <span className={tone === "danger" ? "settings-tile settings-tile-danger" : "settings-tile"}>
        {icon}
      </span>
      <span className="settings-row-text">
        <span className="settings-row-title">{label}</span>
        <span className="settings-row-value">{value}</span>
      </span>
      {end ?? <ChevronRight aria-hidden className="settings-row-chevron" />}
    </button>
  );
}
