"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useAuthStore } from "@/store/authStore";
import { UserResponse } from "@/lib/api/types";
import { useOnboardingState } from "@/components/providers/onboarding-state-context";
import { cefrNames, getAssessmentResult, initializeLearningPlan } from "@/lib/api/assessment-result";
import { startAssessment } from "@/lib/api/assessment";
import { getOnboardingState, onboardingDestination } from "@/lib/api/onboarding-state";

const stages = { WAITING_FOR_WORKER: "Waiting for evaluation", TRANSCRIBING_AUDIO: "Reviewing your recording", EVALUATING_LANGUAGE: "Reviewing your language responses", DETERMINING_PLACEMENT: "Finding your starting level", SAVING_RESULTS: "Saving your feedback", DONE: "Feedback prepared" };
const reasons: Record<string, string> = { MIC_UNAVAILABLE: "Microphone unavailable", DECLINED: "Speaking skipped", TECHNICAL_ISSUE: "Recording issue", INSUFFICIENT_EVIDENCE: "Not enough evidence", AUDIO_UNAVAILABLE: "Audio unavailable", NOT_ASSESSED: "Not assessed", AUDIO_PRONUNCIATION_NOT_EVALUATED: "Pronunciation is not evaluated by this assessment" };

export function AssessmentResult() {
  const { state, refresh } = useOnboardingState();
  return state.active_assessment_id ? <SavedResult key={state.active_assessment_id} id={state.active_assessment_id} /> : <main className="mx-auto max-w-2xl p-8"><p role="alert">We couldn’t locate your saved assessment.</p><button className="journey-primary mt-5" onClick={refresh}>Reload saved state</button></main>;
}
function SavedResult({ id }: { id: string }) {
  const { state, refresh } = useOnboardingState();
  const userId = useAuthStore(store => store.user?.id);
  const router = useRouter();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const restartKey = useRef<string | null>(null);
  const result = useQuery({
    queryKey: ["assessment-result", userId, id],
    queryFn: ({ signal }) => getAssessmentResult(id, signal), retry: false,
    refetchInterval: query => {
      if (query.state.status === "error") return false;
      const data = query.state.data;
      return data && ["SUBMITTED", "PROCESSING", "FAILED_RETRYABLE"].includes(data.status) ? Math.max(1000, (data.retry_after_seconds ?? 5) * 1000) : false;
    },
  });
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (result.data && result.data.status !== state.assessment_status) refresh();
  }, [result.data, state.assessment_status, refresh]);
  const act = async (restart: boolean) => {
    if (controller.current || !userId) return;
    if (restart ? result.data?.status !== "FAILED_FINAL" : result.data?.status !== "COMPLETED" || !result.data.placement?.cefr) return;
    const request = new AbortController(); controller.current = request;
    setBusy(true); setActionError("");
    try {
      if (restart) {
        const storageKey = `assessment-restart:${userId}:${id}`;
        restartKey.current ??= sessionStorage.getItem(storageKey) || crypto.randomUUID();
        sessionStorage.setItem(storageKey, restartKey.current);
        await startAssessment(restartKey.current);
        if (request.signal.aborted) return;
        const next = await getOnboardingState(request.signal);
        try { sessionStorage.removeItem(storageKey); } catch { /* Server state remains authoritative. */ }
        client.setQueriesData({ queryKey: ["onboarding-state", userId] }, next);
        router.replace(onboardingDestination(next));
      } else {
        await initializeLearningPlan(id, request.signal);
        if (request.signal.aborted) return;
        // Do not refetch the current result-route guard before navigating: that
        // would send the learner straight to the dashboard, skipping handoff.
        await client.invalidateQueries({ queryKey: ["onboarding-state", userId], refetchType: "none" });
        client.setQueryData<UserResponse | null>(["currentUser"], profile => profile ? { ...profile, onboarding_status: "COMPLETED" } : profile);
        router.replace("/learning-plan-ready");
      }
    } catch (failure) {
      if (request.signal.aborted) return;
      const response = isAxiosError<{ detail?: string }>(failure) ? failure.response : undefined;
      setActionError(response?.status === 429 ? "Too many requests. Please wait and try again." : response?.data?.detail || (restart ? "We couldn’t confirm the new assessment. Retry safely or check your saved status." : "We couldn’t confirm your plan. Your result is saved; retrying will reuse an existing plan if it was created."));
    } finally { if (controller.current === request) controller.current = null; if (!request.signal.aborted) setBusy(false); }
  };
  if (result.isPending) return <p role="status" className="p-12 text-center">Loading your assessment feedback…</p>;
  if (!result.data) return <main className="mx-auto max-w-2xl p-8"><h1 className="journey-heading">Your feedback couldn’t be loaded.</h1><p role="alert" className="mt-4">Your saved assessment has not been changed.</p><button className="journey-primary mt-6" disabled={result.isFetching} onClick={() => result.refetch()}>Retry</button></main>;
  const data = result.data;
  const placement = data.status === "COMPLETED" ? data.placement : null;
  return <main className="mx-auto max-w-3xl px-5 py-12">
    <section className="rounded-3xl border border-[#dce4d7] bg-white p-6 sm:p-9">
      <p className="journey-eyebrow">YOUR ASSESSMENT</p>
      {result.isError && <p role="alert" className="my-4 rounded-xl bg-orange-50 p-4">We couldn’t refresh your feedback. The last confirmed information is shown below.</p>}
      {placement ? <>
        <h1 className="journey-heading">Here’s a good place to begin.</h1>
        <div className="my-7 rounded-2xl bg-[#edf5ed] p-6"><p className="text-sm text-[#5a685f]">Your provisional English level</p><p className="mt-3 text-3xl font-semibold text-brand-green">{placement.cefr ? `${placement.cefr} — ${cefrNames[placement.cefr]}` : "Overall placement unavailable"}</p><p className="mt-3 text-sm">Confidence: {placement.confidence.toLowerCase()}</p></div>
        <details className="mb-7"><summary className="cursor-pointer py-3 font-medium text-brand-green">Why is this provisional?</summary><p className="mt-2 text-sm leading-7 text-[#5a685f]">This short assessment provides limited evidence and guides your first lessons. It is not an official exam result or certified CEFR qualification.</p></details>
        <h2 className="text-xl font-semibold">Your skill evidence</h2><dl className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(placement.skills).map(([name, skill]) => <div key={name} className="rounded-xl border border-[#dce4d7] p-4"><dt className="font-semibold capitalize">{name}</dt><dd className="mt-2 text-sm leading-6 text-[#5a685f]">{skill.assessed && skill.level ? `${skill.level} — ${cefrNames[skill.level]}` : `Not assessed — ${reasons[skill.reason ?? ""] ?? "Not enough evidence"}`}</dd></div>)}</dl>
        <h2 className="mt-8 text-xl font-semibold">Strengths</h2>{placement.strengths.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-7">{placement.strengths.map((text, index) => <li key={index}>{text}</li>)}</ul> : <p className="mt-3 text-sm text-[#5a685f]">No specific strengths were reported.</p>}
        <h2 className="mt-8 text-xl font-semibold">What to practice next</h2>{placement.improvement_priorities.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-7">{placement.improvement_priorities.map((text, index) => <li key={index}>{text}</li>)}</ul> : <p className="mt-3 text-sm text-[#5a685f]">No specific practice priorities were reported.</p>}
        {!placement.cefr && <p className="mt-6 text-sm">A learning plan needs an overall placement. Your available skill feedback is saved.</p>}
        <button className="journey-primary mt-8" disabled={busy || !placement.cefr} onClick={() => act(false)}>{busy ? "Preparing your plan…" : "Create my learning plan"}</button>
      </> : data.status === "FAILED_FINAL" ? <>
        <h1 className="journey-heading">We couldn’t complete your evaluation.</h1><p role="status" className="mt-5 leading-7 text-[#5a685f]">Your previous attempt has been preserved. You can start a new assessment; this will ask you to answer the activities again.</p><button className="journey-primary mt-7" disabled={busy} onClick={() => act(true)}>{busy ? "Starting…" : "Start a new assessment"}</button>
      </> : <>
        <h1 className="journey-heading">{data.status === "IN_PROGRESS" ? "Your assessment is still in progress." : "We’re preparing your feedback."}</h1><p role="status" className="mt-6 rounded-xl bg-[#edf5ed] p-5">{data.status === "IN_PROGRESS" ? "Return to your saved assessment to finish the activities." : data.evaluation.status === "RETRY_SCHEDULED" || data.status === "FAILED_RETRYABLE" ? "Evaluation will retry automatically. You don’t need to resubmit." : data.evaluation.stage ? stages[data.evaluation.stage] : "Waiting for evaluation"}</p><p className="mt-5 text-sm leading-7 text-[#5a685f]">Your answers are saved. You can leave and return later. This page checks the backend for updates while it is open.</p>
      </>}
      {actionError && <p role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-red-800">{actionError}</p>}
      <div className="mt-7 flex flex-wrap gap-3"><button className="journey-secondary" disabled={result.isFetching || busy} onClick={() => { void result.refetch(); refresh(); }}>{result.isFetching ? "Checking…" : "Check saved status"}</button>{!busy && <Link href="/" className="journey-secondary">Return home</Link>}</div>
    </section>
  </main>;
}
