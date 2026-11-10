import { z } from "zod";
import apiClient from "./axios";

const status = z.enum(["IN_PROGRESS", "SUBMITTED", "PROCESSING", "COMPLETED", "FAILED_RETRYABLE", "FAILED_FINAL"]);
const sectionSchema = z.object({
  skill: z.enum(["GRAMMAR", "VOCABULARY", "WRITING", "SPEAKING"]),
  total_items: z.number().int().positive(), answered_items: z.number().int().nonnegative(), skipped_items: z.number().int().nonnegative(),
}).refine(section => section.answered_items + section.skipped_items <= section.total_items && (section.skill === "SPEAKING" || section.skipped_items === 0), "Section progress is inconsistent.");
const detailSchema = z.object({ id: z.string().uuid(), kind: z.enum(["INITIAL", "REASSESSMENT"]), status, content_release: z.string(), total_items: z.number().int(), answered_items: z.number().int(), current_position: z.number().int().nullable(), can_submit: z.boolean(), sections: z.array(sectionSchema).length(4).refine(sections => new Set(sections.map(section => section.skill)).size === 4) });
const itemSchema = z.object({
  response_id: z.string().uuid(), position: z.number().int(),
  skill: z.enum(["GRAMMAR", "VOCABULARY", "WRITING", "SPEAKING"]),
  kind: z.enum(["MULTIPLE_CHOICE", "SHORT_WRITING", "RECORDED_SPEAKING"]),
  prompt: z.string(), choices: z.array(z.object({ id: z.string(), text: z.string() })).nullish(),
  revision: z.number().int().nonnegative(), optional: z.boolean(), draft_text: z.string().nullish(),
}).refine(item => item.kind !== "MULTIPLE_CHOICE" || !!item.choices?.length, "Question choices are unavailable.");
const savedSchema = z.object({ response_id: z.string().uuid(), status: z.enum(["ASSIGNED", "ANSWERED", "SKIPPED"]), revision: z.number().int().nonnegative(), saved: z.literal(true) });
export type AssessmentItem = z.infer<typeof itemSchema>;
export type AssessmentSnapshot = { detail: z.infer<typeof detailSchema>; item: AssessmentItem | null };
export type AssessmentAnswer = { expected_revision: number } & (
  { kind: "MULTIPLE_CHOICE"; selected_choice_id: string } |
  { kind: "SHORT_WRITING"; text: string; finalize: boolean } |
  { kind: "RECORDED_SPEAKING"; skipped: true; skip_reason: "DECLINED" | "MIC_UNAVAILABLE" | "TECHNICAL_ISSUE" } |
  { kind: "RECORDED_SPEAKING"; media_upload_id: string }
);
export async function startAssessment(key: string) {
  const response = await apiClient.post("/assessments", { kind: "INITIAL" }, { headers: { "Idempotency-Key": key } });
  return z.object({ id: z.string().uuid(), status, estimated_minutes: z.number(), resumed: z.boolean() }).parse(response.data);
}
export async function loadAssessment(id: string, signal?: AbortSignal): Promise<AssessmentSnapshot> {
  const detail = detailSchema.parse((await apiClient.get(`/assessments/${id}`, { signal })).data);
  if (detail.status !== "IN_PROGRESS") return { detail, item: null };
  const response = await apiClient.get(`/assessments/${id}/current-item`, { signal });
  return { detail, item: response.status === 204 ? null : itemSchema.parse(response.data) };
}
export async function assignNextItem(id: string): Promise<AssessmentSnapshot> {
  const response = await apiClient.post(`/assessments/${id}/items/next`);
  const detail = detailSchema.parse((await apiClient.get(`/assessments/${id}`)).data);
  return { detail, item: response.status === 204 ? null : itemSchema.parse(response.data) };
}
export async function saveAssessmentAnswer(id: string, responseId: string, answer: AssessmentAnswer, signal?: AbortSignal) {
  const response = await apiClient.put(`/assessments/${id}/responses/${responseId}`, answer, { signal });
  return savedSchema.parse(response.data);
}

export async function submitAssessment(id: string, key: string, signal?: AbortSignal) {
  const response = await apiClient.post(`/assessments/${id}/submit`, null, { headers: { "Idempotency-Key": key }, signal });
  const result = z.object({
    attempt_id: z.string().uuid(),
    status: z.enum(["SUBMITTED", "PROCESSING", "COMPLETED", "FAILED_RETRYABLE", "FAILED_FINAL"]),
    job_id: z.string().uuid(), result_url: z.string(),
  }).parse(response.data);
  if (result.attempt_id !== id) throw new Error("The submission response did not match the assessment.");
  return result;
}
