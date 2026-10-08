"use client";

import type { ReactNode } from "react";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

interface SideDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  side?: "right" | "left" | "bottom";
  className?: string;
  children: ReactNode;
}

/**
 * Side panel for record details (e.g. a registration) without leaving the list.
 * Full-width on mobile, fixed width on larger screens.
 */
export function SideDrawer({ open, onOpenChange, title, description, footer, side = "right", className, children }: SideDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side={side} className={cn("w-full gap-0 sm:max-w-md data-[side=right]:sm:max-w-md", className)}>
        <SheetHeader className="border-b">
          <SheetTitle>{title}</SheetTitle>
          {description && <SheetDescription>{description}</SheetDescription>}
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <SheetFooter className="border-t">{footer}</SheetFooter>}
      </SheetContent>
    </Sheet>
  );
}
