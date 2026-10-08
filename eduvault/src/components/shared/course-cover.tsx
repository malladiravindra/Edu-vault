import { BarChart3, BookOpen, Briefcase, Code2, Landmark, Palette, ShieldCheck, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const CATEGORY_ICON: Record<string, LucideIcon> = {
  "Data & Analytics": BarChart3,
  "Software Engineering": Code2,
  Cybersecurity: ShieldCheck,
  Business: Briefcase,
  Finance: Landmark,
  Design: Palette,
};

// Restrained, on-brand gradients (indigo/slate family) — no rainbow LMS look.
const GRADIENTS = [
  "from-indigo-600 to-indigo-900",
  "from-slate-700 to-slate-900",
  "from-blue-600 to-indigo-800",
  "from-violet-600 to-indigo-900",
  "from-sky-700 to-slate-900",
  "from-indigo-500 to-slate-800",
];

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

interface CourseCoverProps {
  courseId: string;
  name: string;
  category: string;
  imageUrl?: string;
  className?: string;
  /** Larger icon/typography for banners. */
  variant?: "card" | "banner";
}

/** Course image, with a generated branded cover when no image has been uploaded. */
export function CourseCover({ courseId, name, category, imageUrl, className, variant = "card" }: CourseCoverProps) {
  if (imageUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- remote course images; swap for next/image once domains are known
      <img src={imageUrl} alt="" className={cn("w-full object-cover", className)} />
    );
  }
  const Icon = CATEGORY_ICON[category] ?? BookOpen;
  const gradient = GRADIENTS[hash(courseId) % GRADIENTS.length];
  return (
    <div
      role="img"
      aria-label={`${name} cover`}
      className={cn("relative w-full overflow-hidden bg-gradient-to-br text-white", gradient, className)}
    >
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.12]"
        style={{
          backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
          backgroundSize: "18px 18px",
        }}
      />
      <Icon
        aria-hidden
        className={cn(
          "absolute text-white/15",
          variant === "banner" ? "-right-6 -bottom-10 size-56" : "-right-3 -bottom-5 size-28",
        )}
      />
      <div className={cn("relative flex h-full flex-col justify-end", variant === "banner" ? "p-6 md:p-8" : "p-4")}>
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-0.5 text-[11px] font-medium backdrop-blur-sm">
          <Icon className="size-3" aria-hidden />
          {category}
        </span>
      </div>
    </div>
  );
}
