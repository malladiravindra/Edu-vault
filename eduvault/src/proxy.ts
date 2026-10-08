import { NextResponse, type NextRequest } from "next/server";

/**
 * Optimistic, UX-only route guard (Next.js middleware / proxy).
 *
 * Since the app uses JWT tokens stored in localStorage (not httpOnly cookies),
 * this middleware cannot inspect the token directly. Instead, it checks for a
 * lightweight, non-sensitive `eduvault_role` cookie that the frontend sets after
 * a successful login, and a presence cookie `eduvault_auth` that signals a session
 * exists without exposing the token.
 *
 * This is NOT a security boundary — every API call is authorised server-side by
 * the Django backend. This guard only provides fast, UX-friendly redirects.
 */
const AUTH_PRESENCE_COOKIE = "eduvault_auth";
const ROLE_HINT_COOKIE = "eduvault_role";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const hasAuth = request.cookies.has(AUTH_PRESENCE_COOKIE);
  const role = request.cookies.get(ROLE_HINT_COOKIE)?.value;

  if (!hasAuth) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (pathname.startsWith("/admin") && role === "student") {
    return NextResponse.redirect(new URL("/student/dashboard", request.url));
  }
  if (pathname.startsWith("/student") && role === "admin") {
    return NextResponse.redirect(new URL("/admin/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/student/:path*"],
};
