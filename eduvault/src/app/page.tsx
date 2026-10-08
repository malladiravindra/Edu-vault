import { redirect } from "next/navigation";

/**
 * Entry point. Once the backend exists, `src/proxy.ts` (Next.js 16's renamed
 * middleware) can route signed-in users straight to their portal.
 */
export default function Home() {
  redirect("/login");
}
