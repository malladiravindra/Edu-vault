import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { APP_NAME } from "@/lib/constants";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground", className)}>
      <ShieldCheck className="size-4.5" aria-hidden />
    </span>
  );
}

export function Brand({ href = "/", subtitle, className }: { href?: string; subtitle?: string; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}>
      <BrandMark />
      <span className="leading-tight">
        <span className="block text-[15px] font-semibold tracking-tight">{APP_NAME}</span>
        {subtitle && <span className="block text-[11px] text-muted-foreground">{subtitle}</span>}
      </span>
    </Link>
  );
}
