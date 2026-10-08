"use client";

import { CalendarRange, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface DateRange {
  from?: string;
  to?: string;
}

interface DateRangeFilterProps {
  value: DateRange;
  onChange: (value: DateRange) => void;
  className?: string;
  label?: string;
}

const PRESETS: { label: string; days: number }[] = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
  { label: "Last 12 months", days: 365 },
];

function isoDay(d: Date) {
  return d.toISOString().slice(0, 10);
}

/** Date range picker using native date inputs (accessible, mobile-friendly). Values are YYYY-MM-DD. */
export function DateRangeFilter({ value, onChange, className, label = "Date range" }: DateRangeFilterProps) {
  const active = Boolean(value.from || value.to);
  const summary = active
    ? `${value.from ? formatDate(value.from, "MMM d") : "Start"} – ${value.to ? formatDate(value.to, "MMM d, yyyy") : "Today"}`
    : label;

  return (
    <div className={cn("flex items-center gap-1", className)}>
      <Popover>
        <PopoverTrigger
          render={
            <Button variant="outline" className={cn("h-9 justify-start font-normal", !active && "text-muted-foreground")} />
          }
        >
          <CalendarRange />
          <span className="truncate">{summary}</span>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72">
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <Button
                key={p.days}
                variant="secondary"
                size="sm"
                onClick={() => {
                  const to = new Date();
                  const from = new Date();
                  from.setDate(from.getDate() - p.days);
                  onChange({ from: isoDay(from), to: isoDay(to) });
                }}
              >
                {p.label}
              </Button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="space-y-1.5">
              <Label htmlFor="range-from" className="text-xs">From</Label>
              <Input
                id="range-from"
                type="date"
                value={value.from ?? ""}
                max={value.to}
                onChange={(e) => onChange({ ...value, from: e.target.value || undefined })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="range-to" className="text-xs">To</Label>
              <Input
                id="range-to"
                type="date"
                value={value.to ?? ""}
                min={value.from}
                onChange={(e) => onChange({ ...value, to: e.target.value || undefined })}
              />
            </div>
          </div>
        </PopoverContent>
      </Popover>
      {active && (
        <Button variant="ghost" size="icon-sm" onClick={() => onChange({})} aria-label="Clear date range">
          <X />
        </Button>
      )}
    </div>
  );
}
