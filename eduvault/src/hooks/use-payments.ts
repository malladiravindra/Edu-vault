"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import type { ID, PaymentListParams } from "@/types";
import { paymentApi } from "@/lib/api/paymentApi";
import { queryKeys } from "./query-keys";

export function usePayments(params: PaymentListParams = {}) {
  return useQuery({
    queryKey: queryKeys.payments.list(params),
    queryFn: () => paymentApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useMyPayments(params: PaymentListParams = {}) {
  return useQuery({
    queryKey: queryKeys.payments.mine(params),
    queryFn: () => paymentApi.listMine(params),
    placeholderData: keepPreviousData,
  });
}

export function useCheckoutSummary(courseId: ID | undefined) {
  return useQuery({
    queryKey: queryKeys.payments.checkout(courseId ?? ""),
    queryFn: () => paymentApi.getCheckoutSummary(courseId as ID),
    enabled: Boolean(courseId),
  });
}

/** Creates a hosted checkout session; the caller redirects to `redirectUrl`. */
export function useCreateCheckoutSession() {
  return useMutation({ mutationFn: (courseId: ID) => paymentApi.createCheckoutSession(courseId) });
}
