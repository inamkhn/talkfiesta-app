"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adminContentApi,
  BatchProgress,
  CreateBatchRequest,
  isBatchActive,
  loadRecentBatches,
  RecentBatchEntry,
  RetryBatchRequest,
  saveRecentBatch,
} from "@/lib/api/admin-content";
import { useAuthStore } from "@/store/authStore";

export function useBatchProgress(batchKey: string) {
  const userId = useAuthStore((s) => s.user?.id);

  const query = useQuery({
    queryKey: ["admin-content-batch", batchKey],
    queryFn: ({ signal }) => adminContentApi.getBatch(batchKey, signal),
    enabled: Boolean(batchKey),
    refetchInterval: (q) => (isBatchActive(q.state.data) ? 4000 : false),
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (query.data && userId) {
      saveRecentBatch(userId, query.data);
    }
  }, [query.data, userId]);

  return query;
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  const userId = useAuthStore((s) => s.user?.id);

  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: CreateBatchRequest;
      idempotencyKey: string;
    }) => adminContentApi.createBatch(payload, idempotencyKey),
    onSuccess: (data: BatchProgress) => {
      queryClient.setQueryData(
        ["admin-content-batch", data.generation_batch_key],
        data
      );
      if (userId) {
        saveRecentBatch(userId, data);
      }
    },
  });
}

export function useRetryBatch(batchKey: string) {
  const queryClient = useQueryClient();
  const userId = useAuthStore((s) => s.user?.id);

  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: RetryBatchRequest;
      idempotencyKey: string;
    }) => adminContentApi.retryBatch(batchKey, payload, idempotencyKey),
    onSuccess: (data: BatchProgress) => {
      queryClient.setQueryData(["admin-content-batch", batchKey], data);
      if (userId) {
        saveRecentBatch(userId, data);
      }
    },
  });
}

export function useRecentBatches(): RecentBatchEntry[] {
  const userId = useAuthStore((s) => s.user?.id);
  const [entries, setEntries] = useState<RecentBatchEntry[]>([]);

  useEffect(() => {
    setEntries(loadRecentBatches(userId));
  }, [userId]);

  return entries;
}
