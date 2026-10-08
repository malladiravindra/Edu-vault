"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Pie, PieChart, XAxis, YAxis } from "recharts";
import type { Report } from "@/types";
import { formatCompactNumber, formatCurrency, formatNumber } from "@/lib/format";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

/**
 * Report series names can contain spaces ("Payment Required"), which are not
 * valid in CSS custom property names. Map them to safe keys (s0, s1…) so
 * `var(--color-s0)` works, keeping the original name as the config label.
 */
function normalise(report: Report) {
  const keys = report.series.map((_, i) => `s${i}`);
  const config: ChartConfig = Object.fromEntries(
    report.series.map((name, i) => [keys[i], { label: name, color: COLORS[i % COLORS.length] }]),
  );
  const data = report.chart.map((point) => {
    const next: Record<string, string | number> = { label: point.label };
    report.series.forEach((name, i) => {
      next[keys[i]] = Number(point[name] ?? 0);
    });
    return next;
  });
  return { keys, config, data };
}

function RegistrationsChart({ report }: { report: Report }) {
  const { keys, config, data } = normalise(report);
  return (
    <ChartContainer config={config} className="aspect-auto h-72 w-full">
      <BarChart data={data} margin={{ left: -12, right: 4 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
        <YAxis tickLine={false} axisLine={false} width={44} allowDecimals={false} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        {keys.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            stackId="registrations"
            fill={`var(--color-${key})`}
            radius={i === keys.length - 1 ? [4, 4, 0, 0] : 0}
            maxBarSize={36}
          />
        ))}
      </BarChart>
    </ChartContainer>
  );
}

function RevenueChart({ report }: { report: Report }) {
  const { keys, config, data } = normalise(report);
  const key = keys[0];
  return (
    <ChartContainer config={config} className="aspect-auto h-72 w-full">
      <AreaChart data={data} margin={{ left: 0, right: 8 }}>
        <defs>
          <linearGradient id="revenue-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={`var(--color-${key})`} stopOpacity={0.3} />
            <stop offset="95%" stopColor={`var(--color-${key})`} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={52}
          tickFormatter={(v: number) => `$${formatCompactNumber(v)}`}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              indicator="line"
              formatter={(value, name) => (
                <div className="flex w-full items-center justify-between gap-4">
                  <span className="text-muted-foreground">{config[String(name)]?.label ?? name}</span>
                  <span className="font-mono font-medium text-foreground tabular-nums">
                    {formatCurrency(Number(value) * 100)}
                  </span>
                </div>
              )}
            />
          }
        />
        <Area
          type="monotone"
          dataKey={key}
          stroke={`var(--color-${key})`}
          strokeWidth={2}
          fill="url(#revenue-fill)"
        />
      </AreaChart>
    </ChartContainer>
  );
}

function CoursePopularityChart({ report }: { report: Report }) {
  const { keys, config, data } = normalise(report);
  return (
    <ChartContainer config={config} className="aspect-auto h-96 w-full">
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 12 }} barGap={2}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" />
        <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="label"
          tickLine={false}
          axisLine={false}
          width={150}
          tickFormatter={(v: string) => (v.length > 22 ? `${v.slice(0, 21)}…` : v)}
        />
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        {keys.map((key) => (
          <Bar key={key} dataKey={key} fill={`var(--color-${key})`} radius={[0, 4, 4, 0]} maxBarSize={14} />
        ))}
      </BarChart>
    </ChartContainer>
  );
}

function AccessDistributionChart({ report }: { report: Report }) {
  const valueKey = report.series[0] ?? "Records";
  const slices = report.chart.map((point, i) => ({
    key: `slice${i}`,
    label: point.label,
    value: Number(point[valueKey] ?? 0),
    fill: COLORS[i % COLORS.length],
  }));
  const total = slices.reduce((s, d) => s + d.value, 0);
  const config: ChartConfig = Object.fromEntries(slices.map((s) => [s.label, { label: s.label, color: s.fill }]));

  return (
    <div className="grid items-center gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,16rem)]">
      <div className="relative">
        <ChartContainer config={config} className="mx-auto aspect-square h-64 max-h-64">
          <PieChart>
            <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel nameKey="label" />} />
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius={64}
              outerRadius={100}
              paddingAngle={2}
              strokeWidth={2}
              stroke="var(--card)"
            />
          </PieChart>
        </ChartContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums">{formatNumber(total)}</span>
          <span className="text-xs text-muted-foreground">records</span>
        </div>
      </div>
      <ul className="space-y-2.5" aria-label="Access distribution breakdown">
        {slices.map((s) => {
          const pct = total ? Math.round((s.value / total) * 100) : 0;
          return (
            <li key={s.key} className="flex items-center gap-3 text-sm">
              <span className="size-2.5 shrink-0 rounded-[3px]" style={{ backgroundColor: s.fill }} aria-hidden />
              <span className="min-w-0 flex-1 truncate">{s.label}</span>
              <span className="font-medium tabular-nums">{formatNumber(s.value)}</span>
              <span className="w-10 text-right text-muted-foreground tabular-nums">{pct}%</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ReportChart({ report }: { report: Report }) {
  switch (report.type) {
    case "registrations":
      return <RegistrationsChart report={report} />;
    case "revenue":
      return <RevenueChart report={report} />;
    case "course_popularity":
      return <CoursePopularityChart report={report} />;
    case "access_distribution":
      return <AccessDistributionChart report={report} />;
  }
}
