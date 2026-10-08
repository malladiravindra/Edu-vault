"use client";

import { useCallback, useRef, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import {
  BookOpen,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  CircleCheckBig,
  Clock,
  Ellipsis,
  RefreshCw,
  SendHorizontal,
  Timer,
} from "lucide-react";
import type { StudentCourse } from "@/types";
import { formatDuration } from "@/lib/format";
import { notify } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { useProfile, useStudentDashboard } from "@/hooks/use-students";
import { useMyCourses } from "@/hooks/use-courses";
import { UserAvatar } from "@/components/shared/user-avatar";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";

export function StudentDashboardView() {
  return (
    <div className="stagger-children grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      <StatisticPanel className="md:col-span-2 xl:col-span-1 xl:row-span-2" />
      <CoursesPanel className="md:col-span-2" />
      <StudyProcessPanel />
      <AssistantPanel />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function Panel({ className, children, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn("flex min-w-0 flex-col rounded-[28px] bg-card p-5 text-card-foreground ring-1 ring-foreground/5 sm:p-6", className)}
      {...props}
    >
      {children}
    </section>
  );
}

function PanelHeader({ id, title, action, className }: { id: string; title: string; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <h2 id={id} className="text-xl font-medium tracking-tight">
        {title}
      </h2>
      {action}
    </div>
  );
}

const pillClass =
  "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full px-4 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring";

function PillLink({ href, children, className }: { href: string; children: ReactNode; className?: string }) {
  return (
    <Link href={href} className={cn(pillClass, "bg-muted hover:bg-muted/70", className)}>
      {children}
    </Link>
  );
}

function levelFor(progress: number) {
  if (progress >= 70) return "Advanced";
  if (progress >= 35) return "Intermediate";
  return "Beginner";
}

/** Splits the student's courses into the three buckets shown on the Statistic panel. */
function courseBuckets(courses: StudentCourse[]) {
  return {
    inProgress: courses.filter((c) => c.access === "active" && c.progress < 100).length,
    upcoming: courses.filter((c) => c.access === "pending" || c.access === "payment_required").length,
    completed: courses.filter((c) => c.progress >= 100).length,
  };
}

// ---------------------------------------------------------------------------
// Statistic
// ---------------------------------------------------------------------------

function StatisticPanel({ className }: { className?: string }) {
  const profile = useProfile();
  const dashboard = useStudentDashboard();
  const courses = useMyCourses();

  const loading = profile.isLoading || dashboard.isLoading || courses.isLoading;
  const error = profile.error ?? dashboard.error ?? courses.error;

  return (
    <Panel aria-labelledby="statistic-heading" className={className}>
      <PanelHeader
        id="statistic-heading"
        title="Statistic"
        action={<PillLink href="/student/learning-history">View all</PillLink>}
      />
      {loading ? (
        <StatisticSkeleton />
      ) : error || !profile.data || !dashboard.data ? (
        <ErrorState
          compact
          error={error}
          onRetry={() => {
            profile.refetch();
            dashboard.refetch();
            courses.refetch();
          }}
        />
      ) : (
        <StatisticBody
          name={profile.data.name}
          avatarUrl={profile.data.avatarUrl}
          progress={dashboard.data.overallProgress}
          courses={courses.data ?? []}
        />
      )}
    </Panel>
  );
}

function StatisticBody({
  name,
  avatarUrl,
  progress,
  courses,
}: {
  name: string;
  avatarUrl?: string;
  progress: number;
  courses: StudentCourse[];
}) {
  const firstName = name.split(/\s+/)[0];
  const value = Math.round(Math.min(100, Math.max(0, progress)));
  const { inProgress, upcoming, completed } = courseBuckets(courses);
  const total = inProgress + upcoming + completed;
  const share = (n: number) => (total ? Math.round((n / total) * 100) : 0);

  const segments = [
    { key: "in-progress", label: "In progress", value: share(inProgress), color: "bg-blush" },
    { key: "upcoming", label: "Upcoming", value: share(upcoming), color: "bg-sun" },
    { key: "completed", label: "Completed", value: share(completed), color: "bg-coral" },
  ];

  return (
    <div className="flex flex-1 flex-col">
      <div className="mt-6 flex flex-col items-center text-center">
        <ProgressAvatar name={name} src={avatarUrl} value={value} level={levelFor(value)} />
        <p className="mt-6 text-3xl font-medium tracking-tight">
          Welcome, {firstName} <span aria-hidden>👋</span>
        </p>
      </div>

      <div className="mt-8 flex items-center gap-5">
        <p className="text-6xl font-light tracking-tighter tabular-nums sm:text-7xl">{value}%</p>
        <p className="max-w-32 text-base leading-snug text-muted-foreground">Average course progress</p>
      </div>

      <div className="mt-5" aria-label="Share of your courses by status" role="group">
        <div className="flex gap-2.5">
          {segments.map((s) => (
            <div key={s.key} className="min-w-0 basis-0" style={{ flexGrow: Math.max(s.value, 12) }}>
              <div className={cn("h-1.5 rounded-full", s.color, total === 0 && "opacity-30")} />
              <p className="mt-2 text-sm font-medium tabular-nums">
                {s.value}%<span className="sr-only"> {s.label.toLowerCase()}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-3 rounded-3xl bg-muted/70 py-6 xl:mt-auto">
        <CountTile icon={Timer} tone="bg-blush text-foreground" value={inProgress} label="In progress" />
        <CountTile icon={CalendarClock} tone="bg-sun text-foreground" value={upcoming} label="Upcoming" divider />
        <CountTile icon={CircleCheckBig} tone="bg-coral text-coral-foreground" value={completed} label="Completed" divider />
      </dl>
    </div>
  );
}

function ProgressAvatar({ name, src, value, level }: { name: string; src?: string; value: number; level: string }) {
  // Ring geometry: viewBox 0–100, arc drawn clockwise from 12 o'clock.
  const r = 47;
  const circumference = 2 * Math.PI * r;

  return (
    <div className="relative size-44">
      <svg viewBox="0 0 100 100" className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx="50" cy="50" r={r} fill="none" strokeWidth="2" className="stroke-muted" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - value / 100)}
          className="stroke-coral transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <UserAvatar name={name} src={src} className="absolute inset-4 size-auto *:bg-coral/10 *:text-4xl *:font-light *:text-coral" />
      <span className="absolute bottom-1 left-1/2 -translate-x-1/2 rounded-full bg-coral px-3 py-0.5 text-sm font-medium text-coral-foreground ring-2 ring-card">
        {level}
      </span>
    </div>
  );
}

function CountTile({
  icon: Icon,
  tone,
  value,
  label,
  divider,
}: {
  icon: typeof Timer;
  tone: string;
  value: number;
  label: string;
  divider?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-2 text-center", divider && "border-l border-foreground/10")}>
      <span className={cn("flex size-11 items-center justify-center rounded-full", tone)}>
        <Icon className="size-5" aria-hidden />
      </span>
      <dt className="order-last text-sm text-muted-foreground">{label}</dt>
      <dd className="text-4xl font-light tabular-nums">{value}</dd>
    </div>
  );
}

function StatisticSkeleton() {
  return (
    <div className="flex flex-1 flex-col items-center gap-6 pt-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="size-44 rounded-full" />
      <Skeleton className="h-8 w-52" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-36 w-full rounded-3xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Your courses
// ---------------------------------------------------------------------------

function CoursesPanel({ className }: { className?: string }) {
  const query = useMyCourses();
  const active = (query.data ?? [])
    .filter((c) => c.access === "active")
    .sort((a, b) => (b.lastAccessedAt ?? "").localeCompare(a.lastAccessedAt ?? ""));

  const listRef = useRef<HTMLUListElement | null>(null);
  const [edges, setEdges] = useState({ start: true, end: true });

  // Track whether the carousel can scroll either way, re-measuring on resize.
  const attachList = useCallback((node: HTMLUListElement | null) => {
    listRef.current = node;
    if (!node) return;
    const update = () =>
      setEdges({
        start: node.scrollLeft <= 1,
        end: node.scrollLeft + node.clientWidth >= node.scrollWidth - 1,
      });
    update();
    node.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => {
      node.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, []);

  const scroll = (direction: 1 | -1) => {
    const node = listRef.current;
    if (node) node.scrollBy({ left: direction * node.clientWidth, behavior: "smooth" });
  };

  const navButton =
    "flex size-8 items-center justify-center rounded-full outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-35";

  return (
    <Panel aria-labelledby="courses-heading" className={cn("bg-coral text-coral-foreground ring-0", className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 id="courses-heading" className="text-3xl font-medium tracking-tight sm:text-4xl">
          Your courses
        </h2>
        <div className="flex items-center gap-2">
          {active.length > 1 && (
            <div className="hidden h-9 items-center rounded-full bg-card px-0.5 text-foreground sm:flex">
              <button type="button" className={navButton} onClick={() => scroll(-1)} disabled={edges.start} aria-label="Previous courses">
                <ChevronLeft className="size-4" aria-hidden />
              </button>
              <span className="h-4 w-px bg-border" aria-hidden />
              <button type="button" className={navButton} onClick={() => scroll(1)} disabled={edges.end} aria-label="Next courses">
                <ChevronRight className="size-4" aria-hidden />
              </button>
            </div>
          )}
          <PillLink href="/student/my-courses" className="h-9 bg-card text-foreground hover:bg-card/90">
            View all
          </PillLink>
        </div>
      </div>

      <div className="mt-6 flex-1">
        {query.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className={cn("h-64 rounded-3xl bg-card/40", i > 0 && "hidden sm:block", i > 1 && "sm:hidden lg:block")} />
            ))}
          </div>
        ) : query.error ? (
          <div className="rounded-3xl bg-card text-card-foreground">
            <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
          </div>
        ) : active.length === 0 ? (
          <div className="rounded-3xl bg-card text-card-foreground">
            <EmptyState
              compact
              icon={BookOpen}
              title="No active courses yet"
              description="Request access to a course and it will appear here."
              action={<PillLink href="/student/courses">Browse courses</PillLink>}
            />
          </div>
        ) : (
          <ul
            ref={attachList}
            className="-m-1 flex snap-x snap-mandatory gap-3 overflow-x-auto p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {active.map((c) => (
              <li
                key={c.id}
                className="shrink-0 basis-full snap-start sm:basis-[calc((100%-0.75rem)/2)] lg:basis-[calc((100%-1.5rem)/3)]"
              >
                <CourseTile course={c} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}

function CourseTile({ course }: { course: StudentCourse }) {
  const value = Math.round(Math.min(100, Math.max(0, course.progress)));

  return (
    <Link
      href={`/student/my-courses/${course.id}`}
      className="flex h-full min-h-64 flex-col rounded-3xl bg-card p-5 text-card-foreground outline-none transition-transform duration-200 hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-card focus-visible:ring-offset-2 focus-visible:ring-offset-coral"
    >
      <p className="line-clamp-2 text-xl font-medium tracking-tight">{course.name}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Tag>{course.category}</Tag>
        <Tag>
          {course.resourceCount} {course.resourceCount === 1 ? "resource" : "resources"}
        </Tag>
      </div>

      <div className="mt-auto pt-10">
        <p className="flex items-baseline gap-2">
          <span className="text-xl font-medium tabular-nums">{value}%</span>
          <span className="text-sm text-muted-foreground">completed</span>
        </p>
        <div
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${course.name} progress`}
        >
          <div className="h-full rounded-full bg-coral transition-[width] duration-700 ease-out" style={{ width: `${value}%` }} />
        </div>
      </div>

      <div className="mt-5 flex items-center gap-2.5">
        <UserAvatar name={course.instructor} className="rounded-lg after:rounded-lg *:rounded-lg *:bg-coral/10 *:text-coral" />
        <div className="min-w-0 leading-tight">
          <p className="text-xs text-muted-foreground">Mentor</p>
          <p className="truncate text-sm">{course.instructor}</p>
        </div>
      </div>
    </Link>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-coral/10 px-2.5 py-0.5 text-xs text-foreground/75 ring-1 ring-coral/15">{children}</span>
  );
}

// ---------------------------------------------------------------------------
// Study process
// ---------------------------------------------------------------------------

function StudyProcessPanel({ className }: { className?: string }) {
  const query = useStudentDashboard();
  const data = query.data?.weeklyMinutes ?? [];
  const total = data.reduce((sum, p) => sum + p.value, 0);
  const max = Math.max(...data.map((p) => p.value), 1);
  const peak = data.findIndex((p) => p.value === max);

  return (
    <Panel aria-labelledby="study-heading" className={className}>
      <PanelHeader
        id="study-heading"
        title="Study process"
        action={<span className={cn(pillClass, "border border-foreground/10 text-muted-foreground")}>This week</span>}
      />

      <div className="mt-5 flex-1">
        {query.isLoading ? (
          <Skeleton className="h-60 w-full rounded-2xl" />
        ) : query.error ? (
          <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : total === 0 ? (
          <EmptyState compact icon={Clock} title="No reading time yet" description="Your daily minutes will appear here." />
        ) : (
<ul className="flex h-60 gap-1.5 sm:gap-2" aria-label={`Minutes spent reading per day, ${formatDuration(total)} in total`}>
              {data.map((p, i) => {
                const height = Math.max((p.value / max) * 100, 8);
                const isPeak = i === peak;
                return (
                  <li key={p.label} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                    <div className="relative w-full flex-1 rounded-2xl bg-muted">
                      <div
                        className={cn(
                          "absolute inset-x-0 bottom-0 rounded-2xl transition-[height] duration-700 ease-out",
                          isPeak ? "bg-coral" : "bg-foreground/15",
                        )}
                        style={{ height: `${height}%` }}
                      >
                        <span
                          className={cn(
                            "absolute top-2.5 left-1/2 -translate-x-1/2 rounded-full px-1.5 py-0.5 text-[10px] leading-none font-medium whitespace-nowrap tabular-nums",
                            isPeak ? "bg-foreground text-background" : "bg-coral text-coral-foreground",
                          )}
                        >
                          {p.value}m
                        </span>
                      </div>
                    </div>
                    <span className={cn("text-sm", isPeak ? "font-medium" : "text-muted-foreground")}>
                      <span aria-hidden>{p.label}</span>
                      <span className="sr-only">
                        {p.label}: {p.value} minutes
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
        )}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// AI assistant
// ---------------------------------------------------------------------------

function AssistantPanel({ className }: { className?: string }) {
  const [question, setQuestion] = useState("");

  const comingSoon = () =>
    notify.info("AI assistant is coming soon", "You'll be able to ask questions about your course material here.");

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!question.trim()) return;
    comingSoon();
    setQuestion("");
  };

  const glassButton =
    "inline-flex h-9 items-center justify-center gap-1.5 rounded-full bg-white/85 text-sm font-medium text-neutral-900 shadow-sm outline-none backdrop-blur transition-colors hover:bg-white focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <Panel
      aria-labelledby="assistant-heading"
      className={cn("relative isolate min-h-80 overflow-hidden bg-[#f9c9dc] p-3 ring-0 sm:p-3", className)}
    >
      {/* Decorative "glass" backdrop. */}
      <div aria-hidden className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(120%_90%_at_20%_10%,#fde4ee_0%,#f7b6cf_45%,#f4a3c4_70%,#fbd3e2_100%)]" />
        <div className="absolute -top-10 left-6 size-56 rounded-full bg-[radial-gradient(circle_at_35%_35%,#ffffff_0%,#fbc6da_35%,#ee8fb5_70%,transparent_72%)] opacity-90 blur-[2px]" />
        <div className="absolute top-4 right-10 size-44 rounded-[45%] bg-[radial-gradient(circle_at_60%_30%,#fff5f9_0%,#f6a9c8_45%,#e77aa6_75%,transparent_77%)] opacity-80 blur-[1px]" />
        <div className="absolute -bottom-16 left-1/3 h-40 w-[130%] -translate-x-1/3 rotate-[-8deg] rounded-[50%] bg-[radial-gradient(60%_50%_at_50%_50%,#ffffff_0%,#f9bcd5_50%,transparent_70%)] opacity-80" />
      </div>

      <div className="flex justify-end gap-2 p-2">
        <button type="button" onClick={comingSoon} className={cn(glassButton, "px-4")}>
          <RefreshCw className="size-3.5" aria-hidden />
          Model
        </button>
        <button type="button" onClick={comingSoon} className={cn(glassButton, "w-9")} aria-label="More options">
          <Ellipsis className="size-4" aria-hidden />
        </button>
      </div>

      <div className="mt-auto rounded-3xl bg-card p-5 text-card-foreground shadow-sm">
        <h2 id="assistant-heading" className="text-xl font-medium tracking-tight">
          AI assistant
        </h2>
        <form onSubmit={onSubmit} className="mt-4 flex items-center gap-2 rounded-full bg-muted p-1.5 pl-5">
          <label htmlFor="assistant-question" className="sr-only">
            Ask the AI assistant
          </label>
          <input
            id="assistant-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask something..."
            autoComplete="off"
            className="h-9 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            aria-label="Send question"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-coral text-coral-foreground outline-none transition-opacity hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <SendHorizontal className="size-4" aria-hidden />
          </button>
        </form>
      </div>
    </Panel>
  );
}
