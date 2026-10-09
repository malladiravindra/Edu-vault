/**
 * Auth API — calls the real Django backend.
 *
 * Backend auth flow:
 *  Student login:  POST /api/student/login/             → { user, tokens }
 *  Admin login:    POST /api/admin/login/               → { challenge_token }  (step 1: password)
 *                  POST /api/admin/login/2fa/verify/    → { user, tokens }     (step 2: OTP)
 *
 * After receiving tokens, we:
 *  1. Store access + refresh JWT in localStorage.
 *  2. Set lightweight, non-sensitive presence cookies (`eduvault_auth`, `eduvault_role`)
 *     so the Next.js middleware (proxy.ts) can redirect unauthenticated users without
 *     reading the JWT itself.
 */
import type {
  CurrentUser,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  ResetPasswordRequest,
  TwoFactorRequest,
} from "@/types";
import { http, setTokens, clearTokens } from "./client";

export interface AuthApi {
  login(input: LoginRequest): Promise<LoginResponse>;
  adminLogin(input: LoginRequest): Promise<LoginResponse>;
  studentLogin(input: LoginRequest): Promise<LoginResponse>;
  verifyTwoFactor(input: TwoFactorRequest): Promise<{ user: CurrentUser }>;
  resendTwoFactor(challengeId: string): Promise<void>;
  sendRegistrationOtp(email: string): Promise<{ message?: string; dev_otp?: string } | void>;
  verifyRegistrationOtp(email: string, otp: string): Promise<void>;
  register(input: RegisterRequest): Promise<{ email: string }>;
  forgotPassword(email: string): Promise<void>;
  resetPassword(input: ResetPasswordRequest): Promise<void>;
  logout(): Promise<void>;
  me(): Promise<CurrentUser>;
}

// ---------------------------------------------------------------------------
// Presence cookies (read by the Next.js middleware — not a security boundary)
// ---------------------------------------------------------------------------

export function setPresenceCookies(role: string) {
  if (typeof document === "undefined") return;
  const maxAge = 7 * 24 * 60 * 60; // 7 days (matches refresh token lifetime)
  document.cookie = `eduvault_auth=1; path=/; max-age=${maxAge}; SameSite=Lax`;
  document.cookie = `eduvault_role=${role}; path=/; max-age=${maxAge}; SameSite=Lax`;
}

export function clearPresenceCookies() {
  if (typeof document === "undefined") return;
  document.cookie = "eduvault_auth=; path=/; max-age=0; SameSite=Lax";
  document.cookie = "eduvault_role=; path=/; max-age=0; SameSite=Lax";
}

// ---------------------------------------------------------------------------
// Helper: normalise the backend's snake_case User to the frontend's camelCase
// ---------------------------------------------------------------------------

export function mapUser(raw: Record<string, unknown>): CurrentUser {
  const role = (raw.role as string) ?? "student";
  const fullName = (raw.full_name ?? raw.name ?? "") as string;
  const base = {
    id: (raw.id ?? "") as string,
    name: fullName,
    email: (raw.email ?? "") as string,
    role: role as "admin" | "student",
    twoFactorEnabled: (raw.two_factor_enabled ?? false) as boolean,
    createdAt: (raw.created_at ?? "") as string,
  };
  if (role === "student") {
    return {
      ...base,
      role: "student",
      status: (raw.status ?? "pending") as "active" | "pending" | "suspended",
      phone: (raw.phone_number ?? raw.phone) as string | undefined,
      enrolledCourseIds: [] as string[],
      activeAccessCount: 0,
      totalSpent: 0,
    };
  }
  return { ...base, role: "admin", title: "Administrator" };
}

// ---------------------------------------------------------------------------
// Student auth (JWT returned immediately on correct password — no 2FA)
// ---------------------------------------------------------------------------

export const studentAuthApi = {
  async login({ email, password }: LoginRequest): Promise<LoginResponse> {
    const data = await http.post<{ user: Record<string, unknown>; tokens: { access: string; refresh: string } }>(
      "/student/login/",
      { email, password },
    );
    setTokens(data.tokens.access, data.tokens.refresh);
    const user = mapUser(data.user);
    setPresenceCookies(user.role);
    return { requiresTwoFactor: false, user };
  },

  verifyTwoFactor: () => Promise.reject(new Error("2FA not used for student login.")),
  resendTwoFactor: () => Promise.resolve(),

  async sendRegistrationOtp(email: string): Promise<{ message?: string; dev_otp?: string } | void> {
    const res = await http.post<{ message?: string; dev_otp?: string }>("/student/register/send-otp/", { email });
    return (res as any)?.data ?? res;
  },

  async verifyRegistrationOtp(email: string, otp: string): Promise<void> {
    await http.post("/student/register/verify-otp/", { email, otp });
  },

  async register({ name, email, password, phone }: RegisterRequest): Promise<{ email: string }> {
    const parts = name.trim().split(/\s+/);
    const firstName = parts[0] || "Student";
    const lastName = parts.slice(1).join(" ") || "User";
    const phoneNumber = (phone || "").trim() || "+10000000000";

    await http.post("/student/register/", {
      first_name: firstName,
      last_name: lastName,
      phone_number: phoneNumber,
      email,
      password,
      confirm_password: password,
    });
    return { email };
  },

  async forgotPassword(email: string): Promise<void> {
    await http.post("/accounts/forgot-password/", { email });
  },

  async resetPassword({ token, password }: ResetPasswordRequest): Promise<void> {
    await http.post("/accounts/reset-password/", {
      reset_token: token,
      new_password: password,
      confirm_password: password,
    });
  },

  async logout(): Promise<void> {
    const refresh = typeof localStorage !== "undefined" ? (localStorage.getItem("eduvault_refresh") ?? "") : "";
    try {
      if (refresh) await http.post("/accounts/logout/", { refresh });
    } finally {
      clearTokens();
      clearPresenceCookies();
    }
  },

  me: () => http.get<Record<string, unknown>>("/accounts/me/").then(mapUser) as Promise<CurrentUser>,
};

// ---------------------------------------------------------------------------
// Admin auth (2-step: password → challenge_token, then OTP → JWT tokens)
// ---------------------------------------------------------------------------

export const adminAuthApi = {
  async login({ email, password }: LoginRequest): Promise<LoginResponse> {
    const data = await http.post<{ challenge_token: string; expires_in?: number }>("/admin/login/", { email, password });
    return { requiresTwoFactor: true, challengeId: data.challenge_token };
  },

  async verifyTwoFactor({ challengeId, code }: TwoFactorRequest): Promise<{ user: CurrentUser }> {
    const data = await http.post<{ user: Record<string, unknown>; tokens: { access: string; refresh: string } }>(
      "/admin/login/2fa/verify/",
      { challenge_token: challengeId, otp: code },
    );
    setTokens(data.tokens.access, data.tokens.refresh);
    const user = mapUser(data.user);
    setPresenceCookies(user.role);
    return { user };
  },

  resendTwoFactor: () => Promise.resolve(), // Admin OTP expires after 30s; re-enter credentials for fresh attempt

  register: () => Promise.reject(new Error("Admin accounts cannot self-register.")),

  async forgotPassword(email: string): Promise<void> {
    await http.post("/accounts/forgot-password/", { email });
  },

  async resetPassword({ token, password }: ResetPasswordRequest): Promise<void> {
    await http.post("/accounts/reset-password/", {
      reset_token: token,
      new_password: password,
      confirm_password: password,
    });
  },

  async logout(): Promise<void> {
    const refresh = typeof localStorage !== "undefined" ? (localStorage.getItem("eduvault_refresh") ?? "") : "";
    try {
      if (refresh) await http.post("/accounts/logout/", { refresh });
    } finally {
      clearTokens();
      clearPresenceCookies();
    }
  },

  me: () => http.get<Record<string, unknown>>("/admin/profile/").then(mapUser) as Promise<CurrentUser>,
};

// ---------------------------------------------------------------------------
// Export: dispatch to the right implementation based on context or portal.
// ---------------------------------------------------------------------------

function isAdminPortal(): boolean {
  if (typeof window === "undefined") return false;
  const path = window.location.pathname;
  return path.startsWith("/admin") || path.includes("/login/admin");
}

export const authApi: AuthApi = {
  login: (input) => (isAdminPortal() ? adminAuthApi.login(input) : studentAuthApi.login(input)),
  adminLogin: (input) => adminAuthApi.login(input),
  studentLogin: (input) => studentAuthApi.login(input),
  verifyTwoFactor: (input) => adminAuthApi.verifyTwoFactor(input),
  resendTwoFactor: () => adminAuthApi.resendTwoFactor(),
  sendRegistrationOtp: (email) => studentAuthApi.sendRegistrationOtp(email),
  verifyRegistrationOtp: (email, otp) => studentAuthApi.verifyRegistrationOtp(email, otp),
  register: (input) => studentAuthApi.register(input),
  forgotPassword: (email) => (isAdminPortal() ? adminAuthApi.forgotPassword(email) : studentAuthApi.forgotPassword(email)),
  resetPassword: (input) => (isAdminPortal() ? adminAuthApi.resetPassword(input) : studentAuthApi.resetPassword(input)),
  logout: () => (isAdminPortal() ? adminAuthApi.logout() : studentAuthApi.logout()),
  me: () => (isAdminPortal() ? adminAuthApi.me() : studentAuthApi.me()),
};
