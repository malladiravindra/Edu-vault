import {
  BarChart3,
  Bell,
  BookOpen,
  CreditCard,
  FileText,
  GraduationCap,
  History,
  KeyRound,
  LayoutDashboard,
  Library,
  ScrollText,
  Settings,
  UserPlus,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { UserRole } from "@/types";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Match nested routes as active (default true). */
  matchPrefix?: boolean;
}

export interface NavSection {
  label?: string;
  items: NavItem[];
}

export const ADMIN_NAV: NavSection[] = [
  {
    items: [{ title: "Dashboard", href: "/admin/dashboard", icon: LayoutDashboard }],
  },
  {
    label: "Management",
    items: [
      { title: "Registrations", href: "/admin/registrations", icon: UserPlus },
      { title: "Students", href: "/admin/students", icon: Users },
      { title: "Courses", href: "/admin/courses", icon: BookOpen },
      // Resources live inside each course; this entry opens the course picker.
      { title: "Resources", href: "/admin/resources", icon: FileText },
      { title: "Access", href: "/admin/access", icon: KeyRound },
      { title: "Payments", href: "/admin/payments", icon: CreditCard },
    ],
  },
  {
    label: "Insights",
    items: [
      { title: "Notifications", href: "/admin/notifications", icon: Bell },
      { title: "Audit Logs", href: "/admin/audit-logs", icon: ScrollText },
      { title: "Reports", href: "/admin/reports", icon: BarChart3 },
      { title: "Settings", href: "/admin/settings", icon: Settings },
    ],
  },
];

export const STUDENT_NAV: NavSection[] = [
  {
    items: [
      { title: "Dashboard", href: "/student/dashboard", icon: LayoutDashboard },
      { title: "Courses", href: "/student/courses", icon: Library },
      { title: "My Courses", href: "/student/my-courses", icon: GraduationCap },
      { title: "Payments", href: "/student/payments", icon: CreditCard },
      { title: "Learning History", href: "/student/learning-history", icon: History },
      { title: "Notifications", href: "/student/notifications", icon: Bell },
      { title: "Profile", href: "/student/profile", icon: UserRound },
    ],
  },
];

export const NAV_BY_ROLE: Record<UserRole, NavSection[]> = { admin: ADMIN_NAV, student: STUDENT_NAV };

/** Human labels for static path segments used in breadcrumbs. */
export const SEGMENT_LABELS: Record<string, string> = {
  admin: "Admin",
  student: "Student",
  dashboard: "Dashboard",
  registrations: "Registrations",
  students: "Students",
  courses: "Courses",
  create: "Create",
  resources: "Resources",
  access: "Access Management",
  payments: "Payments",
  checkout: "Checkout",
  notifications: "Notifications",
  "audit-logs": "Audit Logs",
  reports: "Reports",
  settings: "Settings",
  "my-courses": "My Courses",
  "learning-history": "Learning History",
  profile: "Profile",
  view: "Viewer",
  edit: "Edit",
};

/** Intermediate paths that have no page of their own; breadcrumbs render them as plain text. */
const NON_ROUTABLE_PATHS: RegExp[] = [/^\/student\/my-courses\/[^/]+\/resources$/];

export function isRoutablePath(path: string): boolean {
  return !NON_ROUTABLE_PATHS.some((re) => re.test(path));
}

export function isNavItemActive(pathname: string, item: NavItem): boolean {
  if (item.matchPrefix === false) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
