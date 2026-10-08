import { CalendarClock, KeyRound, Tag } from "lucide-react";
import { formatAccessDuration, formatPrice } from "@/lib/format";
import { CourseCover } from "@/components/shared/course-cover";
import { CourseStatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { ACCESS_MODEL_SHORT, parseDuration, type CourseFormValues } from "./course-schema";

/** Live summary of the course being edited, as it will appear in the catalog. */
export function CoursePreviewCard({ values, previewId = "new-course" }: { values: CourseFormValues; previewId?: string }) {
  const name = values.name?.trim() || "Untitled course";
  const category = values.category || "Uncategorized";
  const price = values.accessModel === "free" ? 0 : Math.round((Number.isFinite(values.price) ? values.price : 0) * 100);
  const duration = values.accessDuration ? parseDuration(values.accessDuration) : null;

  const rows = [
    { icon: Tag, label: "Price", value: formatPrice(price) },
    { icon: KeyRound, label: "Access model", value: values.accessModel ? ACCESS_MODEL_SHORT[values.accessModel] : "—" },
    {
      icon: CalendarClock,
      label: "Access duration",
      value: values.accessDuration ? formatAccessDuration(duration) : "—",
    },
  ];

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CourseCover courseId={previewId} name={name} category={category} className="aspect-[16/9]" />
      <CardContent className="space-y-4 py-5">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Preview</p>
            {values.status && <CourseStatusBadge status={values.status} />}
          </div>
          <h2 className="text-base font-semibold text-balance">{name}</h2>
          <p className="line-clamp-3 text-sm text-muted-foreground">
            {values.shortDescription?.trim() || "Your short description will appear here."}
          </p>
        </div>
        <dl className="divide-y rounded-lg border">
          {rows.map((r) => (
            <div key={r.label} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
              <dt className="flex items-center gap-2 text-muted-foreground">
                <r.icon className="size-4" aria-hidden />
                {r.label}
              </dt>
              <dd className="font-medium tabular-nums">{r.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
