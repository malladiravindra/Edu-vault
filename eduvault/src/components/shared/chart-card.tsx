import type { ReactNode } from "react";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ChartCardProps {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

/** Card frame for charts and dashboard panels. */
export function ChartCard({ title, description, action, className, contentClassName, children }: ChartCardProps) {
  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className={cn("min-w-0", contentClassName)}>{children}</CardContent>
    </Card>
  );
}
