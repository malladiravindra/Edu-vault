import { AuthHeroShell } from "@/components/auth/auth-hero-shell";

/** Login, register and forgot password share the photo hero; reset-password and 2FA stay in (auth). */
export default function HeroAuthLayout({ children }: { children: React.ReactNode }) {
  return <AuthHeroShell>{children}</AuthHeroShell>;
}
