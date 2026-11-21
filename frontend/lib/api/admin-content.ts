import axios from "axios";
import apiClient from "./axios";

export interface CreateBatchRequest {
  cefr_level: "B1";
  cycle: 1;
  module: "VOCABULARY";
  goal_variant: "GENERAL";
  day_start: number;
  day_end: number;
  release_key: string;
  dry_run: boolean;
}

export interface ChildProgress {
  job_id: string;
  day: number;
  status: string;
  stage: string;
  attempts: number;
  error_code: string | null;
  lesson_id: string | null;
  item_status: string | null;
  provider_calls_reserved: number;
  remaining_provider_calls: number;
  input_tokens: number;
  output_tokens: number;
}

export interface BatchProgress {
  generation_batch_key: string;
  parent_job_id: string;
  status: string;
  release_key: string;
  dry_run: boolean;
  child_job_count: number;
  children: ChildProgress[];
}

export interface RetryBatchRequest {
  child_job_ids: string[];
  reason: string;
}

export interface RecentBatchEntry {
  batchKey: string;
  releaseKey: string;
  dayStart: number;
  dayEnd: number;
  dryRun: boolean;
  status: string;
  createdAt: string;
}

const TERMINAL_JOB_STATUSES = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

export function isBatchActive(batch: BatchProgress | undefined): boolean {
  if (!batch) return false;
  if (batch.children.length === 0) {
    return !TERMINAL_JOB_STATUSES.has(batch.status);
  }
  return batch.children.some((c) => !TERMINAL_JOB_STATUSES.has(c.status));
}

export function extractAdminApiError(error: unknown): {
  message: string;
  code?: string;
} {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string | { msg?: string }[]; message?: string; code?: string }
      | undefined;
    if (typeof data?.message === "string") {
      return { message: data.message, code: data.code };
    }
    if (typeof data?.detail === "string") {
      return { message: data.detail, code: data.code };
    }
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      return { message: data.detail[0].msg, code: data.code };
    }
    return {
      message: error.message || "Request failed. Please try again.",
      code: data?.code,
    };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: "Unexpected error. Please try again." };
}

export function generateIdempotencyKey(prefix = "admin"): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function storageKey(userId: string): string {
  return `talkfiesta:admin:recent-batches:${userId}`;
}

export function loadRecentBatches(userId: string | undefined): RecentBatchEntry[] {
  if (typeof window === "undefined" || !userId) return [];
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveRecentBatch(
  userId: string | undefined,
  batch: BatchProgress
): RecentBatchEntry[] {
  if (typeof window === "undefined" || !userId) return [];
  const days = batch.children.map((c) => c.day);
  const entry: RecentBatchEntry = {
    batchKey: batch.generation_batch_key,
    releaseKey: batch.release_key,
    dayStart: days.length ? Math.min(...days) : 1,
    dayEnd: days.length ? Math.max(...days) : 1,
    dryRun: batch.dry_run,
    status: batch.status,
    createdAt: new Date().toISOString(),
  };
  const existing = loadRecentBatches(userId).filter(
    (item) => item.batchKey !== batch.generation_batch_key
  );
  const next = [entry, ...existing].slice(0, 20);
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(next));
  } catch {
    // Ignore storage quota errors
  }
  return next;
}

export const adminContentApi = {
  createBatch: async (
    payload: CreateBatchRequest,
    idempotencyKey: string
  ): Promise<BatchProgress> => {
    const res = await apiClient.post<BatchProgress>(
      "/admin/content-generation/batches",
      payload,
      {
        headers: { "Idempotency-Key": idempotencyKey },
      }
    );
    return res.data;
  },

  getBatch: async (
    batchKey: string,
    signal?: AbortSignal
  ): Promise<BatchProgress> => {
    const res = await apiClient.get<BatchProgress>(
      `/admin/content-generation/batches/${encodeURIComponent(batchKey)}`,
      { signal }
    );
    return res.data;
  },

  retryBatch: async (
    batchKey: string,
    payload: RetryBatchRequest,
    idempotencyKey: string
  ): Promise<BatchProgress> => {
    const res = await apiClient.post<BatchProgress>(
      `/admin/content-generation/batches/${encodeURIComponent(batchKey)}/retry`,
      payload,
      {
        headers: { "Idempotency-Key": idempotencyKey },
      }
    );
    return res.data;
  },
};
