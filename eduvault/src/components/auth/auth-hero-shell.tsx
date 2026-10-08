import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { BookOpenText, ChartNoAxesColumnIncreasing, ShieldCheck } from "lucide-react";
import { APP_NAME } from "@/lib/constants";
import { EduVaultLogo } from "./auth-hero-ui";

/**
 * Photo: Julio Lopez on Unsplash (Unsplash License), graded to navy in CSS below.
 * Swap public/images/login-hero.jpg to change it; the gradient shows if it is missing.
 */
const HERO_IMAGE = "/images/login-hero.jpg";

const FEATURES: { icon: LucideIcon; title: string; description: string }[] = [
  { icon: ShieldCheck, title: "Protected Content", description: "Your privacy is our priority" },
  { icon: BookOpenText, title: "Learn at Your Pace", description: "Access anytime, anywhere" },
  { icon: ChartNoAxesColumnIncreasing, title: "Track Your Progress", description: "Build your skills" },
];

/** Full-screen photo, brand panel on the left, and the glass card on the right that holds `children`. */
export function AuthHeroShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-dvh overflow-hidden bg-[#06102a] text-white">
      <div aria-hidden className="absolute inset-0 lg:right-[14%]">
        <div
          className="absolute inset-0 bg-cover bg-[position:78%_center] brightness-[0.8] saturate-[0.85]"
          style={{
            backgroundImage: `url(${HERO_IMAGE}), radial-gradient(ellipse at 45% 40%, #1d3b78 0%, #0c1c45 45%, #06102a 80%)`,
          }}
        />
        {/* Navy night-time grade */}
        <div className="absolute inset-0 bg-[#2a55c0] opacity-70 mix-blend-multiply" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_62%_35%,rgba(255,190,120,0.10)_0%,transparent_45%)]" />
      </div>
      <div
        aria-hidden
        className="absolute inset-0 bg-[linear-gradient(90deg,rgba(6,16,42,0.85)_0%,rgba(6,16,42,0.5)_24%,rgba(6,16,42,0.05)_44%,rgba(6,16,42,0.15)_58%,rgba(6,16,42,0.85)_78%,#06102a_88%)]"
      />
      <div
        aria-hidden
        className="absolute inset-0 bg-[linear-gradient(180deg,rgba(6,16,42,0.35)_0%,transparent_25%,transparent_65%,rgba(6,16,42,0.75)_100%)]"
      />

      {/* On desktop every size scales with viewport height (vh clamps) so the page fits one screen. */}
      <div className="relative mx-auto grid min-h-dvh max-w-[1440px] gap-10 px-4 py-8 sm:px-8 lg:grid-cols-[1fr_minmax(0,clamp(440px,42vw,580px))] lg:items-center lg:gap-8 lg:py-[clamp(16px,3.5vh,40px)] lg:pr-9 lg:pl-[clamp(32px,5vw,72px)]">
        <section className="flex flex-col gap-10 lg:h-full lg:justify-between lg:gap-[clamp(16px,3vh,40px)] lg:py-[clamp(4px,2vh,24px)]">
          <Link
            href="/login"
            className="flex w-fit items-center gap-4 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6]"
          >
            <EduVaultLogo className="size-14 lg:size-[clamp(44px,8vh,84px)]" />
            <span className="text-4xl font-bold tracking-tight lg:text-[clamp(30px,5vh,52px)]">
              Edu<span className="text-[#3b8bff]">Vault</span>
              <span className="sr-only"> — {APP_NAME} home</span>
            </span>
          </Link>

          <div className="hidden space-y-[clamp(10px,2vh,24px)] lg:block">
            <h2 className="text-[clamp(34px,6.4vh,64px)] leading-[1.1] font-bold tracking-tight drop-shadow-[0_2px_12px_rgba(0,0,0,0.4)]">
              Learn
              <br />
              Anytime,
              <br />
              <span className="text-[#3b8bff]">Anywhere</span>
            </h2>
            <p className="max-w-md text-[clamp(16px,2.6vh,26px)] leading-snug text-[#dbe5f7] drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)]">
              Quality courses. Secure access.
              <br />
              Your future, our priority.
            </p>
          </div>

          <ul className="hidden space-y-[clamp(10px,2.8vh,32px)] lg:block">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <li key={title} className="flex items-center gap-[clamp(14px,2vh,24px)]">
                <span className="flex size-[clamp(44px,8vh,82px)] shrink-0 items-center justify-center rounded-full border-2 border-[#2f5bd0] bg-[#0b1f55]/90 shadow-[0_0_24px_rgba(47,107,255,0.25)]">
                  <Icon className="size-[clamp(20px,3.5vh,36px)] text-white" strokeWidth={2.25} aria-hidden />
                </span>
                <span className="drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)]">
                  <span className="block text-[clamp(15px,2.4vh,24px)] font-semibold">{title}</span>
                  <span className="block text-[clamp(13px,2vh,20px)] text-[#c8d4ec]">{description}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <main className="w-full self-center">
          <div className="rounded-3xl border border-[#2a4c9c]/80 bg-[linear-gradient(160deg,rgba(14,31,76,0.94)_0%,rgba(7,18,48,0.96)_100%)] px-6 py-10 shadow-[0_0_0_1px_rgba(59,130,246,0.08),0_30px_80px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(120,160,255,0.12)] sm:px-[60px] sm:py-[76px] lg:px-[clamp(32px,4vw,60px)] lg:py-[clamp(24px,5.5vh,76px)]">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
