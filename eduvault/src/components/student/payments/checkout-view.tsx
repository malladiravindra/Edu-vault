"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BookX,
  CheckCircle2,
  Clock,
  Loader2,
  Lock,
  RotateCw,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { CheckoutSummary } from "@/types";
import { formatAccessDuration, formatCurrency } from "@/lib/format";
import { notify } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { useCheckoutSummary, useCreateCheckoutSession } from "@/hooks/use-payments";
import { useStudentCourse } from "@/hooks/use-courses";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { CourseThumbnail } from "../shared/course-thumbnail";
import { isNotFoundError } from "../shared/utils";

export type CheckoutResultStatus = "success" | "failed" | "cancelled" | "pending";

const SUPPORT_MAILTO = "mailto:support@eduvault.example?subject=Payment%20help";

const checkoutHref = (courseId: string) => `/student/payments/checkout?course=${courseId}`;

interface CheckoutViewProps {
  courseId?: string;
  status?: CheckoutResultStatus;
}

export function CheckoutView({ courseId, status }: CheckoutViewProps) {
  const summary = useCheckoutSummary(courseId);

  const header = (
    <PageHeader
      eyebrow={
        <Link
          href="/student/payments"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground focus-visible:underline focus-visible:outline-none"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Payments
        </Link>
      }
      title="Checkout"
      description="Review your order and complete payment securely."
    />
  );

  if (!courseId) {
    return (
      <div className="space-y-6">
        {header}
        <CourseNotFound />
      </div>
    );
  }

  if (status) {
    // A "pending" result resolves to success once the provider confirms.
    const effective = status === "pending" && summary.data?.paymentStatus === "successful" ? "success" : status;
    return (
      <div className="space-y-6">
        {header}
        <ResultState
          status={effective}
          courseId={courseId}
          courseName={summary.data?.courseName}
          onCheckStatus={() => summary.refetch()}
          checking={summary.isFetching}
        />
      </div>
    );
  }

  let body: ReactNode;
  if (summary.isLoading) {
    body = <CheckoutSkeleton />;
  } else if (summary.error || !summary.data) {
    body = isNotFoundError(summary.error) ? (
      <CourseNotFound />
    ) : (
      <div className="rounded-xl border bg-card">
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} retrying={summary.isFetching} />
      </div>
    );
  } else if (summary.data.paymentStatus === "successful") {
    body = (
      <ResultPanel
        icon={CheckCircle2}
        tone="success"
        title="You've already paid for this course"
        description={`Your payment for ${summary.data.courseName} is complete and your access is active.`}
        actions={
          <>
            <Button nativeButton={false} render={<Link href={`/student/my-courses/${courseId}`} />}>
              Start learning
            </Button>
            <Button variant="outline" nativeButton={false} render={<Link href="/student/payments" />}>
              View receipts
            </Button>
          </>
        }
      />
    );
  } else {
    body = <CheckoutSummaryLayout summary={summary.data} />;
  }

  return (
    <div className="space-y-6">
      {header}
      {body}
    </div>
  );
}

function CheckoutSummaryLayout({ summary }: { summary: CheckoutSummary }) {
  const router = useRouter();
  const course = useStudentCourse(summary.courseId);
  const createSession = useCreateCheckoutSession();
  const [redirecting, setRedirecting] = useState(false);
  const busy = createSession.isPending || redirecting;

  const proceed = () => {
    createSession.mutate(summary.courseId, {
      onSuccess: ({ redirectUrl }) => {
        setRedirecting(true);
        if (redirectUrl.startsWith("/")) router.push(redirectUrl);
        else window.location.assign(redirectUrl);
      },
      onError: (err) => notify.error(err, "Couldn't start checkout"),
    });
  };

  const money = (cents: number) => formatCurrency(cents, summary.currency);

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle className="text-base">
            <h2>Order summary</h2>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center gap-4">
            {course.data ? (
              <CourseThumbnail course={course.data} className="h-16 w-24" />
            ) : (
              <Skeleton className="h-16 w-24 shrink-0 rounded-md" />
            )}
            <div className="min-w-0">
              <p className="font-medium">{summary.courseName}</p>
              <p className="mt-0.5 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <Clock className="size-3.5" aria-hidden />
                {formatAccessDuration(summary.accessDurationDays)}
              </p>
            </div>
          </div>
          <Separator />
          <dl className="space-y-2.5 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Subtotal</dt>
              <dd className="tabular-nums">{money(summary.subtotal)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Tax</dt>
              <dd className="tabular-nums">{money(summary.tax)}</dd>
            </div>
            <Separator />
            <div className="flex items-baseline justify-between gap-3">
              <dt className="font-medium">Total</dt>
              <dd className="text-xl font-semibold tabular-nums">
                {money(summary.total)}{" "}
                <span className="text-xs font-normal text-muted-foreground">{summary.currency}</span>
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2 lg:self-start">
        <CardHeader>
          <CardTitle className="text-base">
            <h2>Payment</h2>
          </CardTitle>
          <CardDescription>
            You&apos;ll be redirected to our secure payment provider to complete your purchase. EduVault never sees or
            stores your card details.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button className="w-full" size="lg" onClick={proceed} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Lock aria-hidden />}
            {busy ? "Redirecting to secure checkout…" : `Proceed to Payment · ${money(summary.total)}`}
          </Button>
        </CardContent>
        <CardFooter className="justify-center gap-2 border-t bg-muted/30 py-3 text-xs text-muted-foreground">
          <ShieldCheck className="size-4 text-success" aria-hidden />
          Secure checkout · Encrypted payment
        </CardFooter>
      </Card>
    </div>
  );
}

interface ResultStateProps {
  status: CheckoutResultStatus;
  courseId: string;
  courseName?: string;
  onCheckStatus: () => void;
  checking: boolean;
}

function ResultState({ status, courseId, courseName, onCheckStatus, checking }: ResultStateProps) {
  const courseLabel = courseName ?? "this course";
  switch (status) {
    case "success":
      return (
        <ResultPanel
          icon={CheckCircle2}
          tone="success"
          title="Payment successful"
          description={`Thanks for your purchase. Access to ${courseLabel} has been granted — you can start learning right away. A receipt is available in your payment history.`}
          actions={
            <>
              <Button nativeButton={false} render={<Link href={`/student/my-courses/${courseId}`} />}>
                Start learning
              </Button>
              <Button variant="outline" nativeButton={false} render={<Link href="/student/payments" />}>
                View receipts
              </Button>
            </>
          }
        />
      );
    case "failed":
      return (
        <ResultPanel
          icon={XCircle}
          tone="danger"
          title="Payment failed"
          description="Your card was not charged. The payment couldn't be completed — please check your details and try again, or contact support if the problem continues."
          actions={
            <>
              <Button nativeButton={false} render={<Link href={checkoutHref(courseId)} />}>
                Try again
              </Button>
              <Button variant="outline" nativeButton={false} render={<a href={SUPPORT_MAILTO} />}>
                Contact support
              </Button>
            </>
          }
        />
      );
    case "cancelled":
      return (
        <ResultPanel
          icon={XCircle}
          tone="neutral"
          title="Payment cancelled"
          description="You cancelled the checkout and haven't been charged. You can complete your purchase whenever you're ready."
          actions={
            <>
              <Button nativeButton={false} render={<Link href={checkoutHref(courseId)} />}>
                Try again
              </Button>
              <Button variant="outline" nativeButton={false} render={<Link href={`/student/courses/${courseId}`} />}>
                Return to course
              </Button>
            </>
          }
        />
      );
    case "pending":
      return (
        <ResultPanel
          icon={Clock}
          tone="warning"
          title="Payment processing"
          description="This can take a minute. We'll notify you as soon as your payment is confirmed and your access is granted."
          actions={
            <Button variant="outline" onClick={onCheckStatus} disabled={checking}>
              <RotateCw className={cn(checking && "animate-spin")} aria-hidden />
              Check status
            </Button>
          }
        />
      );
  }
}

const TONE_CLASS = {
  success: "bg-success/10 text-success",
  danger: "bg-destructive/10 text-destructive",
  warning: "bg-warning/10 text-warning",
  neutral: "bg-muted text-muted-foreground",
} as const;

interface ResultPanelProps {
  icon: LucideIcon;
  tone: keyof typeof TONE_CLASS;
  title: string;
  description: string;
  actions: ReactNode;
}

function ResultPanel({ icon: Icon, tone, title, description, actions }: ResultPanelProps) {
  return (
    <Card className="mx-auto max-w-xl">
      <CardContent className="flex flex-col items-center gap-4 py-8 text-center" role="status">
        <div className={cn("flex size-14 items-center justify-center rounded-full", TONE_CLASS[tone])}>
          <Icon className="size-7" aria-hidden />
        </div>
        <div className="space-y-1.5">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex flex-wrap justify-center gap-2 pt-1">{actions}</div>
      </CardContent>
    </Card>
  );
}

function CourseNotFound() {
  return (
    <div className="rounded-xl border bg-card">
      <EmptyState
        icon={BookX}
        title="Course not found"
        description="We couldn't find the course for this checkout. Choose a course from your list to continue."
        action={
          <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/student/my-courses" />}>
            Go to My Courses
          </Button>
        }
      />
    </div>
  );
}

function CheckoutSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-5" aria-busy="true" aria-label="Loading">
      <Card className="lg:col-span-3">
        <CardContent className="space-y-4">
          <Skeleton className="h-5 w-32" />
          <div className="flex gap-4">
            <Skeleton className="h-16 w-24" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/3" />
            </div>
          </div>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardContent className="space-y-4">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}
