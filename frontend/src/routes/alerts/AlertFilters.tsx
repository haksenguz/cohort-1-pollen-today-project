/** Horizontally scrolling filter chips: All, Unread, then one per alert type. */
import { typeLabel } from "./alertModel";

export interface FilterOption {
  key: string;
  label: string;
  count: number;
}

export function buildFilterOptions(
  alerts: { alert_type: string; is_read: boolean }[],
  types: string[],
): FilterOption[] {
  const options: FilterOption[] = [
    { key: "all", label: "All", count: alerts.length },
    { key: "unread", label: "Unread", count: alerts.filter((a) => !a.is_read).length },
  ];
  for (const t of types) {
    options.push({
      key: t,
      label: typeLabel(t),
      count: alerts.filter((a) => a.alert_type === t).length,
    });
  }
  return options;
}

export function AlertFilters({
  options,
  active,
  onSelect,
}: {
  options: FilterOption[];
  active: string;
  onSelect: (key: string) => void;
}) {
  return (
    <div className="al-chips" role="group" aria-label="Filter alerts">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          className="al-chip-filter"
          aria-pressed={active === o.key}
          onClick={() => onSelect(o.key)}
        >
          <span>{o.label}</span>
          <span className="al-chip-n">{o.count}</span>
        </button>
      ))}
    </div>
  );
}
