"use client";
import Link from "next/link";
import { useOnboardingState } from "@/components/providers/onboarding-state-context";

// State routing is live. Assessment activities and result rendering are the
// next integration task; sample answers/results remain on /design-preview only.
export function AssessmentResume() {
  const { state, refresh, isRefreshing } = useOnboardingState();
  const processing = state.next_step === "ASSESSMENT_PROCESSING";
  const title = state.next_step === "ASSESSMENT_RESULT" ? "Your assessment result is ready."
    : state.next_step === "ASSESSMENT_RETRY" ? "Your assessment couldn’t be completed."
    : processing ? "Your assessment is being processed."
    : state.active_assessment_id ? "Welcome back to your level check."
    : "You’re ready for your level check.";
  const description = processing ? "Your submitted answers are saved. You can leave and return; this page checks for status changes automatically."
    : state.next_step === "ASSESSMENT_RESULT" ? "Your result is saved. The result report and learning-plan handoff are not available on this page yet."
    : state.next_step === "ASSESSMENT_RETRY" ? "Your previous attempt has been preserved. Starting a new attempt is not available on this page yet."
    : state.active_assessment_id ? "Your existing assessment was found. Continuing its questions is not available on this page yet."
    : "Your preferences are saved. Starting the live assessment is not available on this page yet.";
  return <main className="mx-auto max-w-2xl px-5 py-14"><section className="rounded-3xl border border-[#dce4d7] bg-white p-7 sm:p-10"><p className="journey-eyebrow">ENGLISH LEVEL CHECK</p><h1 className="journey-heading">{title}</h1><p role="status" className="mt-5 leading-7 text-[#5a685f]">{description}</p><div className="mt-8 flex flex-wrap gap-3"><button className="journey-primary" disabled={isRefreshing} onClick={refresh}>{isRefreshing ? "Checking…" : "Check saved status"}</button>{state.next_step === "ASSESSMENT" && !state.active_assessment_id && <Link href="/goal-selection" className="journey-secondary">Edit preferences</Link>}<Link href="/" className="journey-secondary">Return home</Link></div></section></main>;
}
