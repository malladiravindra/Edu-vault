"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import type { LoginRequest, RegisterRequest, ResetPasswordRequest, TwoFactorRequest } from "@/types";
import { authApi } from "@/lib/api/authApi";
import { queryKeys } from "./query-keys";

/** Current session user. UI convenience only — the backend enforces authorisation. */
export function useCurrentUser() {
  return useQuery({ queryKey: queryKeys.auth.me, queryFn: () => authApi.me(), staleTime: 5 * 60_000 });
}

export function useLogin() {
  return useMutation({ mutationFn: (input: LoginRequest) => authApi.login(input) });
}

export function useStudentLogin() {
  return useMutation({ mutationFn: (input: LoginRequest) => authApi.studentLogin(input) });
}

export function useAdminLogin() {
  return useMutation({ mutationFn: (input: LoginRequest) => authApi.adminLogin(input) });
}

export function useSendRegistrationOtp() {
  return useMutation({ mutationFn: (email: string) => authApi.sendRegistrationOtp(email) });
}

export function useVerifyRegistrationOtp() {
  return useMutation({ mutationFn: ({ email, otp }: { email: string; otp: string }) => authApi.verifyRegistrationOtp(email, otp) });
}

export function useVerifyTwoFactor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TwoFactorRequest) => authApi.verifyTwoFactor(input),
    onSuccess: ({ user }) => qc.setQueryData(queryKeys.auth.me, user),
  });
}

export function useResendTwoFactor() {
  return useMutation({ mutationFn: (challengeId: string) => authApi.resendTwoFactor(challengeId) });
}

export function useRegister() {
  return useMutation({ mutationFn: (input: RegisterRequest) => authApi.register(input) });
}

export function useForgotPassword() {
  return useMutation({ mutationFn: (email: string) => authApi.forgotPassword(email) });
}

export function useResetPassword() {
  return useMutation({ mutationFn: (input: ResetPasswordRequest) => authApi.resetPassword(input) });
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: () => authApi.logout(),
    onSettled: () => {
      qc.clear();
      router.replace("/login");
    },
  });
}
