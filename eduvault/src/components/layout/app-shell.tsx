"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Menu } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import type { UserRole } from "@/types";
import { NAV_BY_ROLE, isNavItemActive, type NavSection } from "@/lib/navigation";
import { useLogout } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { AppBreadcrumbs, BreadcrumbProvider } from "./breadcrumbs";
import { Brand } from "./brand";
import { NotificationBell } from "./notification-bell";
import { UserMenu } from "./user-menu";

const navLinkClass =
  "inline-flex h-9 items-center gap-1 rounded-md px-3 text-sm font-medium whitespace-nowrap text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring";
const navLinkActiveClass = "bg-muted text-foreground";

/**
 * Desktop navigation: every module as a direct link beside the brand. Scrolls
 * sideways (scrollbar hidden) if the window is too narrow to fit them all.
 */
function DesktopNav({ sections }: { sections: NavSection[] }) {
  const pathname = usePathname();
  const items = sections.flatMap((section) => section.items);

  return (
    <nav
      aria-label="Main"
      className="hidden min-w-0 flex-1 items-center gap-0.5 overflow-x-auto [scrollbar-width:none] lg:flex [&::-webkit-scrollbar]:hidden"
    >
      {items.map((item) => {
        const active = isNavItemActive(pathname, item);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(navLinkClass, "relative shrink-0 px-2.5", active && "text-foreground")}
          >
            {item.title}
            {/* Active indicator: grows out from the centre when the link becomes current. */}
            <span
              aria-hidden
              className={cn(
                "absolute inset-x-2.5 -bottom-px h-0.5 origin-center rounded-full bg-primary transition-transform duration-300 ease-out",
                active ? "scale-x-100" : "scale-x-0",
              )}
            />
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * Student desktop navigation: links grouped in a rounded "pill track"; the
 * current page is a dark pill with its icon.
 */
function PillNav({ sections }: { sections: NavSection[] }) {
  const pathname = usePathname();
  const items = sections.flatMap((section) => section.items);

  return (
    <nav
      aria-label="Main"
      className="mx-auto hidden min-w-0 items-center gap-0.5 overflow-x-auto rounded-full bg-muted p-1 [scrollbar-width:none] lg:flex [&::-webkit-scrollbar]:hidden"
    >
      {items.map((item) => {
        const active = isNavItemActive(pathname, item);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full px-4 text-sm font-medium whitespace-nowrap text-foreground/80 outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
              active && "bg-foreground text-background hover:text-background",
            )}
          >
            {active && <item.icon className="size-4" aria-hidden />}
            {item.title}
          </Link>
        );
      })}
    </nav>
  );
}

/** Mobile navigation: every section listed in an off-canvas sheet. */
function MobileNav({ role, sections, home }: { role: UserRole; sections: NavSection[]; home: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const logout = useLogout();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button variant="ghost" size="icon" className="-ml-2 lg:hidden" aria-label="Open navigation" />}>
        <Menu />
      </SheetTrigger>
      <SheetContent side="left" className="gap-0 p-0">
        <SheetHeader className="h-16 justify-center border-b">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <Brand href={home} subtitle={role === "admin" ? "Admin Console" : "Student Portal"} />
        </SheetHeader>
        <nav aria-label="Main" className="flex-1 overflow-y-auto p-3">
          {sections.map((section, i) => (
            <div key={section.label ?? i} className="stagger-children mb-3">
              {section.label && (
                <p className="px-3 pb-1 text-xs font-medium text-muted-foreground">{section.label}</p>
              )}
              {section.items.map((item) => {
                const active = isNavItemActive(pathname, item);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    onClick={() => setOpen(false)}
                    className={cn(navLinkClass, "flex w-full gap-2.5", active && navLinkActiveClass)}
                  >
                    <item.icon className="size-4" aria-hidden />
                    {item.title}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="border-t p-3">
          <button
            type="button"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className={cn(navLinkClass, "flex w-full gap-2.5 disabled:opacity-50")}
          >
            <LogOut className="size-4" aria-hidden />
            Log out
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

interface AppShellProps {
  role: UserRole;
  children: ReactNode;
}

/**
 * Portal chrome shared by Admin and Student: sticky top navbar with the brand,
 * inline module links (off-canvas menu on mobile), notifications and the
 * account menu; breadcrumbs sit above the page content.
 */
export function AppShell({ role, children }: AppShellProps) {
  const pathname = usePathname();
  const sections = NAV_BY_ROLE[role];
  const home = role === "admin" ? "/admin/dashboard" : "/student/dashboard";
  // The student portal uses a floating rounded navbar over a grey canvas.
  const floating = role === "student";

  return (
    <BreadcrumbProvider>
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-background px-3 py-2 text-sm font-medium focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>
      <div className={cn("flex min-h-svh flex-col", floating && "bg-canvas")}>
        <header
          className={cn(
            "sticky top-0 z-30 animate-in fade-in slide-in-from-top-2 duration-500",
            floating
              ? "px-4 pt-3 md:px-6 lg:px-8 lg:pt-4"
              : "border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70",
          )}
        >
          <div
            className={cn(
              "flex h-16 w-full items-center gap-4",
              floating
                ? "mx-auto max-w-[1400px] rounded-full bg-card/90 pr-3 pl-4 shadow-sm ring-1 ring-foreground/5 backdrop-blur lg:gap-6"
                : "px-4 md:px-6 lg:gap-6 lg:px-8",
            )}
          >
            <MobileNav role={role} sections={sections} home={home} />
            <Brand href={home} subtitle={role === "admin" ? "Admin Console" : "Student Portal"} className="shrink-0" />
            {floating ? <PillNav sections={sections} /> : <DesktopNav sections={sections} />}
            <div className={cn("flex shrink-0 items-center gap-1 sm:gap-2", floating ? "ml-auto lg:ml-0" : "ml-auto")}>
              <NotificationBell scope={role} />
              <UserMenu role={role} />
            </div>
          </div>
        </header>
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1400px] flex-1 p-4 outline-none md:p-6 lg:p-8"
        >
          {/* Keyed by route so each page fades in on navigation. */}
          <div key={pathname} className="animate-in fade-in slide-in-from-bottom-2 duration-300 ease-out">
            <div className="mb-4 empty:hidden">
              <AppBreadcrumbs />
            </div>
            {children}
          </div>
        </main>
      </div>
    </BreadcrumbProvider>
  );
}
