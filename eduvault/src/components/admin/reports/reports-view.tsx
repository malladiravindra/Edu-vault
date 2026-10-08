"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Download, FileBarChart, FileSpreadsheet, FileText, Loader2, RotateCcw } from "lucide-react";
import type { ExportFormat, Report, ReportFilters, ReportRow, ReportType } from "@/types";
import { formatCurrency, formatNumber, formatRelative } from "@/lib/format";
import { notify } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { useExportReport, useReport } from "@/hooks/use-reports";
import { useCourses } from "@/hooks/use-courses";
import { PageHeader } from "@/components/shared/page-header";
import { ChartCard } from "@/components/shared/chart-card";
import { StatCard } from "@/components/shared/stat-card";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { DateRangeFilter, type DateRange } from "@/components/shared/date-range-filter";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { ChartSkeleton, StatCardsSkeleton, TableSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReportChart } from "./report-chart";

const REPORT_TABS: { value: ReportType; label: string; chartTitle: string; chartDescription: string }[] = [
  {
    value: "registrations",
    label: "Registration Report",
    chartTitle: "Registrations by month",
    chartDescription: "Immediate access, payment required and pending registrations",
  },
  {
    value: "revenue",
    label: "Revenue Report",
    chartTitle: "Revenue over time",
    chartDescription: "Gross revenue from successful payments (USD)",
  },
  {
    value: "course_popularity",
    label: "Course Popularity",
    chartTitle: "Top courses",
    chartDescription: "Total enrolments compared with currently active learners",
  },
  {
    value: "access_distribution",
    label: "Access Distribution",
    chartTitle: "Access by status",
    chartDescription: "Share of access records in each status",
  },
];

const EXPORT_FORMATS: { value: ExportFormat; label: string; icon: typeof FileText }[] = [
  { value: "csv", label: "CSV", icon: FileText },
  { value: "xlsx", label: "Excel", icon: FileSpreadsheet },
  { value: "pdf", label: "PDF", icon: FileBarChart },
];

const CURRENCY_KEYS = new Set(["Revenue"]);
const PERCENT_KEYS = new Set(["share", "completion"]);

function formatCell(key: string, value: string | number | undefined) {
  if (value === undefined) return "—";
  if (typeof value !== "number") return value;
  if (CURRENCY_KEYS.has(key)) return formatCurrency(value * 100); // report revenue rows are whole dollars
  if (PERCENT_KEYS.has(key)) return `${value}%`;
  return formatNumber(value);
}

function buildColumns(report: Report): DataTableColumn<ReportRow>[] {
  return report.columns.map((col, i) => {
    const numeric = report.rows.some((r) => typeof r[col.key] === "number");
    return {
      id: col.key,
      header: col.label,
      align: numeric ? "right" : "left",
      hideBelow: !numeric && i > 0 ? "md" : undefined,
      className: numeric ? "tabular-nums" : i === 0 ? "font-medium" : "text-muted-foreground",
      cell: (row) => formatCell(col.key, row[col.key]),
    };
  });
}

function ReportContent({ report, meta }: { report: Report; meta: (typeof REPORT_TABS)[number] }) {
  const columns = useMemo(() => buildColumns(report), [report]);
  const firstKey = report.columns[0]?.key ?? "label";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {report.summary.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} className="[&_p:nth-child(2)]:truncate" />
        ))}
      </div>

      <ChartCard title={meta.chartTitle} description={meta.chartDescription}>
        {report.chart.length === 0 ? (
          <EmptyState compact title="No chart data" description="No data matches the selected filters." />
        ) : (
          <ReportChart report={report} />
        )}
      </ChartCard>

      <section className="space-y-3" aria-labelledby={`${report.type}-table-heading`}>
        <h2 id={`${report.type}-table-heading`} className="text-base font-semibold">
          Report data
        </h2>
        <DataTable
          columns={columns}
          data={report.rows}
          getRowId={(row) => String(row[firstKey])}
          emptyIcon={FileBarChart}
          emptyTitle="No rows to show"
          emptyDescription="No data matches the selected filters."
          caption={`${report.title} data`}
        />
      </section>
    </div>
  );
}

function ReportLoading() {
  return (
    <div className="space-y-6">
      <StatCardsSkeleton />
      <ChartSkeleton />
      <Card className="py-0">
        <TableSkeleton rows={6} columns={4} />
      </Card>
    </div>
  );
}

export function ReportsView() {
  const [tab, setTab] = useState<ReportType>("registrations");
  const [range, setRange] = useState<DateRange>({});
  const [courseId, setCourseId] = useState<string | undefined>();
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null);

  const filters: ReportFilters = { ...range, courseId };
  const query = useReport(tab, filters);
  const courses = useCourses({ pageSize: 100 });
  const exportReport = useExportReport();

  const courseOptions = (courses.data?.data ?? []).map((c) => ({ value: c.id, label: c.name }));
  const hasFilters = Boolean(range.from || range.to || courseId);
  const meta = REPORT_TABS.find((t) => t.value === tab) ?? REPORT_TABS[0];
  // keepPreviousData keeps the old tab's report around while switching; only show matching data.
  const report = query.data?.type === tab ? query.data : undefined;

  function handleExport(format: ExportFormat) {
    const title = report?.title ?? meta.label;
    const label = EXPORT_FORMATS.find((f) => f.value === format)?.label ?? format.toUpperCase();
    setExportingFormat(format);
    notify.info("Preparing export", `Generating your ${title} (${label})…`);
    exportReport.mutate(
      { type: tab, format, filters },
      {
        onSuccess: () => notify.success("Export ready", `Your ${title} report (${label}) has been generated.`),
        onError: (err) => notify.error(err, "Couldn't export report"),
        onSettled: () => setExportingFormat(null),
      },
    );
  }

  const exportingLabel = EXPORT_FORMATS.find((f) => f.value === exportingFormat)?.label;

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <PageHeader
          title="Reports"
          description="Analyse registrations, revenue, course performance and access across the platform"
          actions={
            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button variant="outline" disabled={exportReport.isPending || !report} />}
              >
                {exportReport.isPending ? <Loader2 className="animate-spin" /> : <Download />}
                {exportReport.isPending ? `Exporting ${exportingLabel ?? ""}…` : "Export"}
                {!exportReport.isPending && <ChevronDown className="text-muted-foreground" />}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Export {meta.label.toLowerCase()}</DropdownMenuLabel>
                  {EXPORT_FORMATS.map((f) => (
                    <DropdownMenuItem key={f.value} onClick={() => handleExport(f.value)}>
                      <f.icon />
                      {f.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          }
        />
        {report && (
          <p className="text-xs text-muted-foreground">
            Generated <time dateTime={report.generatedAt}>{formatRelative(report.generatedAt)}</time>
          </p>
        )}
      </div>

      <DataTableToolbar>
        <DateRangeFilter value={range} onChange={setRange} />
        <FilterDropdown
          label="Course"
          allLabel="All courses"
          value={courseId}
          onChange={setCourseId}
          options={courseOptions}
          className="sm:w-56"
        />
        <Button
          variant="ghost"
          size="sm"
          disabled={!hasFilters}
          onClick={() => {
            setRange({});
            setCourseId(undefined);
          }}
        >
          <RotateCcw />
          Reset
        </Button>
      </DataTableToolbar>

      <Tabs value={tab} onValueChange={(v) => setTab(v as ReportType)} className="gap-6">
        <div className="-mx-4 overflow-x-auto border-b px-4 sm:mx-0 sm:px-0">
          <TabsList variant="line">
            {REPORT_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="px-3">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        {REPORT_TABS.map((t) => (
          <TabsContent key={t.value} value={t.value}>
            {query.isError && !report ? (
              <Card>
                <ErrorState
                  error={query.error}
                  title="We couldn't load this report"
                  onRetry={() => query.refetch()}
                  retrying={query.isFetching}
                />
              </Card>
            ) : !report ? (
              <ReportLoading />
            ) : (
              <div
                className={cn("transition-opacity", query.isFetching && "pointer-events-none opacity-60")}
                aria-busy={query.isFetching}
              >
                <ReportContent report={report} meta={t} />
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
