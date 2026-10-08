"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useCreateCourse } from "@/hooks/use-courses";
import { notify } from "@/lib/toast";
import { PageHeader } from "@/components/shared/page-header";
import { CourseForm } from "./course-form";
import { CoursePreviewCard } from "./course-preview-card";

export function CourseCreateView() {
  const router = useRouter();
  const create = useCreateCourse();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          <Link
            href="/admin/courses"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            Courses
          </Link>
        }
        title="Create course"
        description="Set up the course details, pricing and access rules. You can add PDF resources after it's created."
      />

      <CourseForm
        mode="create"
        isPending={create.isPending}
        onCancel={() => router.push("/admin/courses")}
        onSubmit={async (input) => {
          try {
            const course = await create.mutateAsync(input);
            notify.success("Course created", course.name);
            router.push(`/admin/courses/${course.id}`);
            return true;
          } catch (err) {
            notify.error(err, "Couldn't create course");
            return false;
          }
        }}
        renderAside={(values) => <CoursePreviewCard values={values} />}
      />
    </div>
  );
}
