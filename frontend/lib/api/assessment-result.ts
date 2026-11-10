import { z } from "zod";
import apiClient from "./axios";

export const cefrNames = { A1: "Beginner", A2: "Elementary", B1: "Intermediate", B2: "Upper intermediate", C1: "Advanced", C2: "Proficient" } as const;
const cefr = z.enum(["A1", "A2", "B1", "B2", "C1", "C2"]);
const skill = z.object({ level: cefr.nullable(), assessed: z.boolean(), reason: z.string().nullish() }).refine(value => value.assessed ? value.level !== null && !value.reason : value.level === null && !!value.reason);
const failure = z.object({ code: z.string(), message: z.string(), retryable: z.boolean() });
const resultSchema = z.object({
  assessment_id: z.string().uuid(),
  status: z.enum(["IN_PROGRESS", "SUBMITTED", "PROCESSING", "COMPLETED", "FAILED_RETRYABLE", "FAILED_FINAL"]),
  evaluation: z.object({
    job_id: z.string().uuid().nullable(),
    status: z.enum(["NOT_STARTED", "QUEUED", "RUNNING", "RETRY_SCHEDULED", "SUCCEEDED", "FAILED_FINAL"]),
    stage: z.enum(["WAITING_FOR_WORKER", "TRANSCRIBING_AUDIO", "EVALUATING_LANGUAGE", "DETERMINING_PLACEMENT", "SAVING_RESULTS", "DONE"]).nullable(),
    error: failure.nullish(),
  }),
  placement: z.object({
    cefr: cefr.nullable(), provisional: z.literal(true), confidence: z.enum(["LOW", "MEDIUM", "HIGH"]),
    skills: z.object({ grammar: skill, vocabulary: skill, writing: skill, speaking: skill, pronunciation: z.object({ assessed: z.literal(false), level: z.null(), reason: z.literal("AUDIO_PRONUNCIATION_NOT_EVALUATED") }) }),
    strengths: z.array(z.string()).max(20), improvement_priorities: z.array(z.string()).max(20), rubric_version: z.string(), assessment_version: z.string().nullish(),
  }).nullable(),
  retry_after_seconds: z.number().int().positive().nullable(), error: failure.nullish(),
}).refine(result => result.status !== "COMPLETED" || result.placement !== null);
export async function getAssessmentResult(id: string, signal?: AbortSignal) {
  const result = resultSchema.parse((await apiClient.get(`/assessments/${id}/result`, { signal })).data);
  if (result.assessment_id !== id) throw new Error("Unexpected assessment result.");
  return result;
}
export async function initializeLearningPlan(id: string, signal?: AbortSignal) {
  const response = await apiClient.post("/onboarding/complete", { assessment_attempt_id: id }, { signal });
  return z.object({ status: z.literal("COMPLETED"), learning_plan_id: z.string().uuid(), next_path: z.literal("/dashboard") }).parse(response.data);
}
const moduleName = z.enum(["SPEAKING", "VOCABULARY", "WRITING"]);
const currentPlanSchema = z.object({
  plan: z.object({ id: z.string().uuid(), cycle: z.number().int().positive(), status: z.literal("ACTIVE"), placement_cefr: cefr, placement_provisional: z.literal(true), goals: z.array(z.enum(["FLUENCY", "BUSINESS", "EXAM", "TRAVEL"])), focus_areas: z.array(moduleName), daily_target_minutes: z.number().positive() }),
  modules: z.array(z.object({ module: moduleName, current_day: z.number().int().min(1).max(21), total_days: z.literal(21), status: z.enum(["ACTIVE", "AWAITING_CONTENT", "COMPLETED"]), prioritized: z.boolean() })).min(1).max(3),
});
const todaySchema = z.object({ plan_id: z.string().uuid(), activities: z.array(z.object({ module: moduleName, day: z.number().int().min(1).max(21), title: z.string().nullable(), description: z.string().nullable(), estimated_minutes: z.number().positive().nullable(), activity_status: z.enum(["NOT_STARTED", "IN_PROGRESS", "COMPLETED"]) })).min(1).max(3) });
export async function getPlanHandoff(signal?: AbortSignal) {
  const [planResponse, todayResponse] = await Promise.all([
    apiClient.get("/learning-plans/current", { signal }),
    apiClient.get("/learning-plans/current/today", { signal }),
  ]);
  const plan = currentPlanSchema.parse(planResponse.data);
  const today = todaySchema.parse(todayResponse.data);
  if (plan.plan.id !== today.plan_id) throw new Error("Your plan changed while loading. Please reload.");
  return { ...plan, activities: today.activities };
}
