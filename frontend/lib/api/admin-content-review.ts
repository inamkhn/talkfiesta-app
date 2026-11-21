import apiClient from "./axios";

export type ContentStatus = "DRAFT" | "REVIEW" | "PUBLISHED" | "ARCHIVED";
export type ReviewAction = "APPROVE" | "REQUEST_CHANGES" | "PUBLISH" | "ARCHIVE";

export interface ContentItemSummary {
  id: string;
  kind: string;
  module: string | null;
  release_key: string;
  cycle: number | null;
  day: number | null;
  cefr_level: string | null;
  goal_variant: string | null;
  title: string;
  status: ContentStatus;
  origin: "HUMAN" | "AI";
  generation_batch_key: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
  published_at: string | null;
}

export interface LinkedWordItem {
  id: string;
  title: string;
  status: ContentStatus;
  cefr_level: string | null;
  body: Record<string, unknown>;
}

export interface AiReviewSummary {
  review_decision: string | null;
  review_scores: Record<string, number> | null;
  warnings: string[];
}

export interface ContentItemDetail extends ContentItemSummary {
  body: Record<string, unknown>;
  words: LinkedWordItem[];
  ai_review: AiReviewSummary | null;
}

export interface ContentItemListResponse {
  items: ContentItemSummary[];
  total: number;
}

export interface ContentItemFilters {
  status?: string;
  release_key?: string;
  generation_batch_key?: string;
  origin?: string;
  limit?: number;
}

export const adminContentReviewApi = {
  listItems: async (
    filters: ContentItemFilters = {},
    signal?: AbortSignal
  ): Promise<ContentItemListResponse> => {
    const params: Record<string, string | number> = {};
    if (filters.status) params.status = filters.status;
    if (filters.release_key) params.release_key = filters.release_key;
    if (filters.generation_batch_key) {
      params.generation_batch_key = filters.generation_batch_key;
    }
    if (filters.origin) params.origin = filters.origin;
    if (filters.limit) params.limit = filters.limit;

    const res = await apiClient.get<ContentItemListResponse>(
      "/admin/content/items",
      { params, signal }
    );
    return res.data;
  },

  getItem: async (
    itemId: string,
    signal?: AbortSignal
  ): Promise<ContentItemDetail> => {
    const res = await apiClient.get<ContentItemDetail>(
      `/admin/content/items/${encodeURIComponent(itemId)}`,
      { signal }
    );
    return res.data;
  },

  decide: async (
    itemId: string,
    action: ReviewAction,
    reviewNotes?: string
  ): Promise<ContentItemDetail> => {
    const res = await apiClient.post<ContentItemDetail>(
      `/admin/content/items/${encodeURIComponent(itemId)}/decision`,
      {
        action,
        review_notes: reviewNotes?.trim() || null,
      }
    );
    return res.data;
  },
};
