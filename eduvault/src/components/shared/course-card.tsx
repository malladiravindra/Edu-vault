"use client";

import Link from "next/link";
import { FileText, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import type { StudentCourse } from "@/types";
import { getCourseCta } from "@/lib/course-access";
import { formatAccessDuration, formatPrice } from "@/lib/format";
import { CourseCover } from "./course-cover";
import { AccessStatusBadge } from "./status-badge";

interface CourseCardProps {
  course: StudentCourse;
  /** Called when the CTA is "Request Access" (no href). */
  onRequestAccess?: (course: StudentCourse) => void;
}

export function CourseCard({ course, onRequestAccess }: CourseCardProps) {
  const cta = getCourseCta(course.id, course.access);

  return (
    <Card className="group gap-0 overflow-hidden pt-0 transition-all duration-200 hover:-translate-y-1 hover:shadow-md">
      <Link href={`/student/courses/${course.id}`} className="block focus-visible:outline-none" tabIndex={-1} aria-hidden>
        <CourseCover courseId={course.id} name={course.name} category={course.category} imageUrl={course.imageUrl} className="aspect-[16/7]" />
      </Link>
      <CardContent className="flex flex-1 flex-col gap-3 pt-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="leading-snug font-semibold">
            <Link href={`/student/courses/${course.id}`} className="hover:underline focus-visible:underline focus-visible:outline-none">
              {course.name}
            </Link>
          </h3>
          {course.access !== "none" && <AccessStatusBadge status={course.access} />}
        </div>
        <p className="line-clamp-2 text-sm text-muted-foreground">{course.shortDescription}</p>
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <FileText className="size-3.5" aria-hidden />
            {course.resourceCount} resources
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3.5" aria-hidden />
            {formatAccessDuration(course.accessDurationDays)}
          </span>
        </div>
      </CardContent>
      <CardFooter className="mt-4 justify-between gap-3 border-t bg-muted/30 py-3">
        <span className="text-base font-semibold tabular-nums">{formatPrice(course.price, course.currency)}</span>
        {cta.href ? (
          <Button size="sm" variant={cta.variant} nativeButton={false} render={<Link href={cta.href} />}>
            {cta.cardLabel}
          </Button>
        ) : (
          <Button
            size="sm"
            variant={cta.variant}
            disabled={cta.disabled}
            onClick={cta.kind === "request" ? () => onRequestAccess?.(course) : undefined}
          >
            {cta.cardLabel}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
