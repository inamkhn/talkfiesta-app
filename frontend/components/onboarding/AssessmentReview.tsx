"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { Check } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { AssessmentSnapshot, submitAssessment } from "@/lib/api/assessment";
import { getOnboardingState, onboardingDestination } from "@/lib/api/onboarding-state";

type Props = { detail: AssessmentSnapshot["detail"]; onReload: () => Promise<void> };
export function AssessmentReview({ detail, onReload }: Props) {
  const router = useRouter();
  const client = useQueryClient();
  const userId = useAuthStore(store => store.user?.id);
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState("");
  const [needsReview, setNeedsReview] = useState(false);
  const operation = useRef<AbortController | null>(null);
  const key = useRef<string | null>(null);
  const confirmed = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const complete = detail.can_submit && detail.sections.every(section => section.answered_items + section.skipped_items === section.total_items);
  useEffect(() => {
    heading.current?.focus();
    return () => operation.current?.abort();
  }, []);
  const finish = async () => {
    if (operation.current || !userId || (!confirmed.current && (!complete || needsReview))) return;
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true); setError("");
    try {
      if (!confirmed.current) {
        const storageKey = `assessment-submit:${userId}:${detail.id}`;
        key.current ??= sessionStorage.getItem(storageKey) || crypto.randomUUID();
        // Persist before sending. Lost responses and page reloads reuse this key.
        sessionStorage.setItem(storageKey, key.current);
        await submitAssessment(detail.id, key.current, controller.signal);
        confirmed.current = true;
        setAccepted(true);
        // Failure to clear browser storage must not turn acceptance into failure.
        try { sessionStorage.removeItem(storageKey); } catch { /* Accepted by server. */ }
        await client.invalidateQueries({ queryKey: ["assessment", userId, detail.id], refetchType: "none" });
      }
      const state = await getOnboardingState(controller.signal);
      if (controller.signal.aborted) return;
      if (state.next_step === "PREFERENCES" || state.next_step === "ASSESSMENT") {
        throw new Error("Your submission was accepted. Its status is still updating; check again shortly.");
      }
      // Update all cached paths before routing, avoiding a stale guard redirect
      // back to editable questions. Never navigate to an untrusted result_url.
      client.setQueriesData({ queryKey: ["onboarding-state", userId] }, state);
      router.replace(onboardingDestination(state));
    } catch (failure) {
      if (controller.signal.aborted) return;
      if (confirmed.current) {
        setError("Your assessment was submitted, but we couldn’t open its current status. Check again; you don’t need to submit twice.");
      } else if (isAxiosError<{ code?: string; detail?: string }>(failure)) {
        const status = failure.response?.status;
        if (status === 409) {
          setNeedsReview(true);
          setError(failure.response?.data?.detail || "The assessment changed. Reload its saved status before continuing.");
        } else if (status === 429) {
          setError("Too many requests. Wait a moment, then try again. Your answers are saved.");
        } else {
          setError("We couldn’t confirm submission. Your answers are saved. Retry safely, or check the saved status.");
        }
      } else {
        setError("We couldn’t confirm submission. Please retry or check the saved status. Your answers have not been cleared.");
      }
    } finally {
      if (operation.current === controller) operation.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return <>
    <p className="journey-eyebrow">FINAL REVIEW</p>
    <h1 ref={heading} tabIndex={-1} className="journey-heading outline-none">{accepted ? "Your assessment is submitted." : "Ready to see your starting level?"}</h1>
    <p className="mt-5 leading-7 text-[#5a685f]">{accepted ? "Your answers are frozen and evaluation has been queued. You can leave and return while processing continues." : "Your saved activity status is listed below. Finish assessment will freeze them and queue evaluation to prepare your provisional starting level."}</p>
    <ul className="my-7 divide-y divide-[#e0e5db]">{detail.sections.map(section => {
      const done = section.answered_items + section.skipped_items === section.total_items;
      const label = section.skill.charAt(0) + section.skill.slice(1).toLowerCase();
      const description = section.skill === "SPEAKING" && section.skipped_items > 0 ? "Skipped — not assessed" : section.skill === "SPEAKING" && done ? "Recording saved" : done ? "Completed" : "Incomplete";
      return <li key={section.skill} className="flex flex-wrap items-center justify-between gap-3 py-4"><span className="flex items-center gap-2 font-semibold">{done && <Check size={18} className="text-brand-green" aria-hidden="true" />}{label}</span><span className="text-sm text-[#5a685f]">{description}</span></li>;
    })}</ul>
    {!accepted && <p className="text-sm leading-7 text-[#5a685f]">Finalized answers cannot be edited. Leaving now keeps your answers saved without submitting them.</p>}
    {error && <p role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}
    {accepted && <p role="status" className="mt-5 text-brand-green">Submission accepted. {busy ? "Opening status…" : "You can check its status again below."}</p>}
    <div className="mt-8 flex flex-wrap gap-3">
      <button className="journey-primary" disabled={busy || (!accepted && (!complete || needsReview))} onClick={finish}>{busy ? accepted ? "Opening status…" : "Submitting…" : accepted ? "Open assessment status" : "Finish assessment"}</button>
      {!accepted && error && <button className="journey-secondary" disabled={busy} onClick={onReload}>Reload saved status</button>}
      {!busy && <Link href="/" className="journey-secondary">{accepted ? "Return home" : "Save & exit"}</Link>}
    </div>
  </>;
}
