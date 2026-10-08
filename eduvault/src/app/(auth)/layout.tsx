import { CheckCircle2 } from "lucide-react";
import { Brand } from "@/components/layout/brand";

const HIGHLIGHTS = [
  "Protected, watermarked course materials",
  "Approval and payment workflows built in",
  "Progress tracking across every resource",
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,560px)] xl:grid-cols-[1fr_640px]">
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-indigo-700 via-indigo-800 to-slate-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="absolute inset-0 opacity-[0.08]"
          style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "22px 22px" }}
        />
        <Brand href="/login" className="relative [&_span]:text-white" />
        <div className="relative max-w-md space-y-6">
          <h2 className="text-3xl leading-tight font-semibold tracking-tight">
            Secure learning, managed with confidence.
          </h2>
          <ul className="space-y-3 text-indigo-100">
            {HIGHLIGHTS.map((h) => (
              <li key={h} className="flex items-center gap-3 text-sm">
                <CheckCircle2 className="size-4.5 shrink-0 text-indigo-300" aria-hidden />
                {h}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-indigo-200/80">© {new Date().getFullYear()} EduVault. All rights reserved.</p>
      </aside>
      <main className="flex flex-col bg-background">
        <div className="p-6 lg:hidden">
          <Brand href="/login" />
        </div>
        <div className="flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
          <div className="w-full max-w-sm">{children}</div>
        </div>
      </main>
    </div>
  );
}
