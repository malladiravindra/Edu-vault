import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  /** Percentage change vs previous period. */
  trend?: number;
  /** Set when a decrease is good news (e.g. pending items). */
  invertTrend?: boolean;
  hint?: string;
  className?: string;
}

export function StatCard({ label, value, icon: Icon, trend, invertTrend, hint, className }: StatCardProps) {
  const positive = trend !== undefined && (invertTrend ? trend < 0 : trend >= 0);
  return (
    <Card className={cn("gap-0 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md", className)}>
      <CardContent className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
          {(trend !== undefined || hint) && (
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              {trend !== undefined && (
                <span
                  className={cn(
                    "inline-flex items-center gap-0.5 font-medium",
                    positive ? "text-success" : "text-destructive",
                  )}
                >
                  {trend >= 0 ? <ArrowUpRight className="size-3.5" aria-hidden /> : <ArrowDownRight className="size-3.5" aria-hidden />}
                  {Math.abs(trend).toFixed(1)}%
                  <span className="sr-only">{trend >= 0 ? "increase" : "decrease"}</span>
                </span>
              )}
              {hint && <span className="truncate">{hint}</span>}
            </p>
          )}
        </div>
        {Icon && (
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/8 text-primary">
            <Icon className="size-4.5" aria-hidden />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
