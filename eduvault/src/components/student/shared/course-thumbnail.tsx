import type { StudentCourse } from "@/types";
import { CourseCover } from "@/components/shared/course-cover";
import { cn } from "@/lib/utils";

/** Small course cover without the category chip, for list rows. */
export function CourseThumbnail({
  course,
  className,
}: {
  course: Pick<StudentCourse, "id" | "name" | "category" | "imageUrl">;
  className?: string;
}) {
  return (
    <CourseCover
      courseId={course.id}
      name={course.name}
      category={course.category}
      imageUrl={course.imageUrl}
      className={cn("h-14 w-20 shrink-0 rounded-md [&>div:last-child]:hidden", className)}
    />
  );
}
