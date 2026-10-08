"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const ALL = "__all__";

export interface FilterOption<V extends string = string> {
  value: V;
  label: string;
}

interface FilterDropdownProps<V extends string> {
  /** Accessible label and the "All …" option text, e.g. "Status" → "All statuses". */
  label: string;
  allLabel?: string;
  value: V | undefined;
  onChange: (value: V | undefined) => void;
  options: FilterOption<V>[];
  className?: string;
}

/**
 * Single-select filter with an "All" option that maps to `undefined`.
 * Wraps Base UI Select so pages never deal with its null/items details.
 */
export function FilterDropdown<V extends string>({
  label,
  allLabel,
  value,
  onChange,
  options,
  className,
}: FilterDropdownProps<V>) {
  const allText = allLabel ?? `All ${label.toLowerCase()}`;
  const items = [{ value: ALL, label: allText }, ...options];

  return (
    <Select
      items={items}
      value={value ?? ALL}
      onValueChange={(v) => onChange(!v || v === ALL ? undefined : (v as V))}
    >
      <SelectTrigger aria-label={label} className={cn("h-9 w-full sm:w-44", className)}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {items.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
