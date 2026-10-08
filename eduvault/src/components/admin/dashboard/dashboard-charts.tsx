"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import type { MultiSeriesPoint, TimeSeriesPoint } from "@/types";
import { formatCurrency } from "@/lib/format";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { ChartCard } from "@/components/shared/chart-card";
import { EmptyState } from "@/components/shared/empty-state";

// ---------------------------------------------------------------------------
// Registration overview — stacked bars by month
// ---------------------------------------------------------------------------

const registrationConfig = {
  approved: { label: "Approved", color: "var(--chart-1)" },
  paymentRequired: { label: "Payment Required", color: "var(--chart-2)" },
  pending: { label: "Pending", color: "var(--chart-3)" },
} satisfies ChartConfig;

/** API series names (with spaces) → CSS-safe chart keys. */
const REGISTRATION_SERIES: Record<keyof typeof registrationConfig, string> = {
  approved: "Approved",
  paymentRequired: "Payment Required",
  pending: "Pending",
};

function toNumber(v: string | number | undefined): number {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n : 0;
}

export function RegistrationOverviewChart({ data, className }: { data: MultiSeriesPoint[]; className?: string }) {
  const rows = data.map((p) => ({
    label: p.label,
    approved: toNumber(p[REGISTRATION_SERIES.approved]),
    paymentRequired: toNumber(p[REGISTRATION_SERIES.paymentRequired]),
    pending: toNumber(p[REGISTRATION_SERIES.pending]),
  }));

  return (
    <ChartCard title="Registration overview" description="Registrations by outcome, last 12 months" className={className}>
      {rows.length === 0 ? (
        <EmptyState compact title="No registrations yet" />
      ) : (
        <ChartContainer config={registrationConfig} className="aspect-auto h-64 w-full">
          <BarChart data={rows} margin={{ left: -16, right: 4, top: 4 }} accessibilityLayer>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
            <YAxis tickLine={false} axisLine={false} width={44} allowDecimals={false} />
            <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Bar dataKey="approved" stackId="r" fill="var(--color-approved)" maxBarSize={28} />
            <Bar dataKey="paymentRequired" stackId="r" fill="var(--color-paymentRequired)" maxBarSize={28} />
            <Bar dataKey="pending" stackId="r" fill="var(--color-pending)" radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ChartContainer>
      )}
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Revenue overview — area (values are whole dollars, not cents)
// ---------------------------------------------------------------------------

const revenueConfig = {
  value: { label: "Revenue", color: "var(--chart-1)" },
} satisfies ChartConfig;

function formatDollarsAxis(v: number): string {
  return v >= 1000 ? `$${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : `$${v}`;
}

export function RevenueOverviewChart({ data, className }: { data: TimeSeriesPoint[]; className?: string }) {
  return (
    <ChartCard title="Revenue overview" description="Successful payments, last 12 months" className={className}>
      {data.length === 0 ? (
        <EmptyState compact title="No revenue yet" />
      ) : (
        <ChartContainer config={revenueConfig} className="aspect-auto h-64 w-full">
          <AreaChart data={data} margin={{ left: -8, right: 8, top: 4 }} accessibilityLayer>
            <defs>
              <linearGradient id="dashboard-revenue-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-value)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="var(--color-value)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
            <YAxis tickLine={false} axisLine={false} width={52} tickFormatter={formatDollarsAxis} />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  indicator="line"
                  formatter={(value) => (
                    <div className="flex w-full items-center justify-between gap-4">
                      <span className="text-muted-foreground">Revenue</span>
                      <span className="font-mono font-medium text-foreground tabular-nums">
                        {formatCurrency(Number(value) * 100)}
                      </span>
                    </div>
                  )}
                />
              }
            />
            <Area
              dataKey="value"
              type="monotone"
              stroke="var(--color-value)"
              strokeWidth={2}
              fill="url(#dashboard-revenue-fill)"
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ChartContainer>
      )}
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Course popularity — horizontal bars
// ---------------------------------------------------------------------------

const popularityConfig = {
  value: { label: "Enrolments", color: "var(--chart-2)" },
} satisfies ChartConfig;

const MAX_COURSE_LABEL = 22;

function truncate(label: string): string {
  return label.length > MAX_COURSE_LABEL ? `${label.slice(0, MAX_COURSE_LABEL - 1)}…` : label;
}

export function CoursePopularityChart({ data, className }: { data: TimeSeriesPoint[]; className?: string }) {
  return (
    <ChartCard title="Course popularity" description="Top courses by enrolments" className={className}>
      {data.length === 0 ? (
        <EmptyState compact title="No enrolments yet" />
      ) : (
        <ChartContainer config={popularityConfig} className="aspect-auto h-64 w-full">
          <BarChart data={data} layout="vertical" margin={{ left: 0, right: 12 }} accessibilityLayer>
            <CartesianGrid horizontal={false} strokeDasharray="3 3" />
            <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="label"
              tickLine={false}
              axisLine={false}
              width={150}
              tick={{ fontSize: 11 }}
              tickFormatter={truncate}
            />
            <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="line" />} />
            <Bar dataKey="value" fill="var(--color-value)" radius={[0, 4, 4, 0]} maxBarSize={22} />
          </BarChart>
        </ChartContainer>
      )}
    </ChartCard>
  );
}
