"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adminContentReviewApi,
  ContentItemFilters,
  ReviewAction,
} from "@/lib/api/admin-content-review";

export function useAdminContentItems(filters: ContentItemFilters) {
  return useQuery({
    queryKey: ["admin-content-items", filters],
    queryFn: ({ signal }) => adminContentReviewApi.listItems(filters, signal),
    refetchOnWindowFocus: true,
  });
}

export function useAdminContentItem(itemId: string) {
  return useQuery({
    queryKey: ["admin-content-item", itemId],
    queryFn: ({ signal }) => adminContentReviewApi.getItem(itemId, signal),
    enabled: Boolean(itemId),
  });
}

export function useContentReviewDecision(itemId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      action,
      reviewNotes,
    }: {
      action: ReviewAction;
      reviewNotes?: string;
    }) => adminContentReviewApi.decide(itemId, action, reviewNotes),
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin-content-item", itemId], updated);
      void queryClient.invalidateQueries({ queryKey: ["admin-content-items"] });
    },
  });
}
