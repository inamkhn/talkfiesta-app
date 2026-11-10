"use client";
import Link from "next/link";
import { AssessmentReview } from "./AssessmentReview";
import { AssessmentSpeaking } from "./AssessmentSpeaking";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { isAxiosError } from "axios";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useOnboardingState } from "@/components/providers/onboarding-state-context";
import { AssessmentAnswer, AssessmentItem, assignNextItem, loadAssessment, saveAssessmentAnswer, startAssessment } from "@/lib/api/assessment";

function requestError(error: unknown): string {
  if (isAxiosError<{ detail?: string }>(error)) {
    if (error.response?.status === 429) return "Too many requests. Wait a moment and try again.";
    if (error.response?.status === 409) return "Your assessment changed elsewhere. Reload its saved state before continuing.";
    if (typeof error.response?.data?.detail === "string") return error.response.data.detail;
  }
  return "We couldn’t confirm this request. Your current answer is still here. Please try again.";
}

export function AssessmentFlow() {
  const { state, refresh } = useOnboardingState();
  const userId = useAuthStore(store => store.user?.id);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const running = useRef(false);
  const requestKey = useRef<string | null>(null);
  const attemptId = state.active_assessment_id ?? createdId;
  const start = async () => {
    if (running.current || !userId) return;
    running.current = true; setBusy(true); setError("");
    try {
      const storageKey = `assessment-start:${userId}`;
      requestKey.current ??= sessionStorage.getItem(storageKey) || crypto.randomUUID();
      sessionStorage.setItem(storageKey, requestKey.current);
      const attempt = await startAssessment(requestKey.current);
      sessionStorage.removeItem(storageKey);
      if (attempt.status === "IN_PROGRESS") setCreatedId(attempt.id);
      refresh();
    } catch (failure) { setError(requestError(failure)); }
    finally { running.current = false; setBusy(false); }
  };
  if (attemptId) return <AssessmentAttempt key={attemptId} id={attemptId} />;
  return <main className="mx-auto max-w-2xl px-5 py-12"><section className="rounded-3xl border border-[#dce4d7] bg-white p-8"><p className="journey-eyebrow">ENGLISH LEVEL CHECK</p><h1 className="journey-heading">Let’s discover your starting level.</h1><p className="mt-5 leading-7 text-[#5a685f]">Short grammar, vocabulary, and writing activities help choose suitable first lessons. Speaking is optional. Allow around 5–7 minutes; there is no countdown.</p><p className="mt-4 text-sm leading-7 text-[#5a685f]">Your result will be provisional, not a certified qualification. Final answers cannot be edited, but you can save a writing draft before finalizing it.</p>{error && <p role="alert" className="mt-5 text-red-800">{error}</p>}<div className="mt-8 flex flex-wrap gap-3"><button className="journey-primary" disabled={busy} onClick={start}>{busy ? "Starting…" : "Start assessment"}</button><Link href="/goal-selection" className="journey-secondary">Edit preferences</Link></div></section></main>;
}

function AssessmentAttempt({ id }: { id: string }) {
  const { refresh } = useOnboardingState();
  const userId = useAuthStore(store => store.user?.id);
  const client = useQueryClient();
  const queryKey = ["assessment", userId, id];
  const snapshot = useQuery({ queryKey, queryFn: ({ signal }) => loadAssessment(id, signal), retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false, staleTime: 0 });
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState("");
  const running = useRef(false);
  const next = async () => {
    if (running.current) return;
    running.current = true; setAdvancing(true); setError("");
    try { client.setQueryData(queryKey, await assignNextItem(id)); }
    catch (failure) { setError(requestError(failure)); if (isAxiosError(failure) && failure.response?.status === 409) refresh(); }
    finally { running.current = false; setAdvancing(false); }
  };
  const reload = async () => { setError(""); await snapshot.refetch(); refresh(); };
  useEffect(() => {
    if (snapshot.data && snapshot.data.detail.status !== "IN_PROGRESS") refresh();
  }, [snapshot.data, refresh]);
  if (snapshot.isPending || snapshot.isFetching) return <p role="status" className="p-12 text-center">Loading your saved assessment…</p>;
  if (snapshot.isError) return <main className="mx-auto max-w-2xl p-8"><p role="alert">We couldn’t load your assessment. Saved answers have not been changed.</p><button className="journey-primary mt-5" onClick={() => snapshot.refetch()}>Retry</button></main>;
  const { detail, item } = snapshot.data;
  if (detail.status !== "IN_PROGRESS") return <p role="status" className="p-12 text-center">Checking your assessment status…</p>;
  return <main className="mx-auto max-w-3xl px-5 py-10">
    <p className="journey-eyebrow">ENGLISH LEVEL CHECK</p>
    <ol aria-label="Assessment sections" className="my-6 grid grid-cols-2 gap-3 sm:grid-cols-4">{["GRAMMAR", "VOCABULARY", "WRITING", "SPEAKING"].map(skill => <li key={skill} aria-current={item?.skill === skill ? "step" : undefined} className={`border-t-4 py-3 text-sm ${item?.skill === skill ? "border-brand-green font-semibold text-brand-green" : "border-[#dce4d7] text-[#5a685f]"}`}>{skill.charAt(0) + skill.slice(1).toLowerCase()}{skill === "SPEAKING" && " (optional)"}</li>)}</ol>
    {error && <p role="alert" className="mb-5 rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}
    <section className="rounded-3xl border border-[#dce4d7] bg-white p-6 sm:p-9">
      {item ? (item.kind === "RECORDED_SPEAKING" ? <AssessmentSpeaking key={`${item.response_id}:${item.revision}`} id={id} item={item} advancing={advancing} onNext={next} onReload={reload} /> : <AnswerForm key={`${item.response_id}:${item.revision}`} id={id} item={item} advancing={advancing} onNext={next} onReload={reload} />) : detail.can_submit ? <AssessmentReview detail={detail} onReload={reload} /> : <>
        <h1 className="journey-heading">Ready for your next activity?</h1>
        <p className="mt-5 text-[#5a685f]">Continue to receive your next assigned question.</p>
        <div className="mt-7 flex flex-wrap gap-3">{!detail.can_submit && <button className="journey-primary" disabled={advancing} onClick={next}>{advancing ? "Loading…" : "Continue assessment"}</button>}<Link className="journey-secondary" href="/">Save & exit</Link></div>
      </>}
    </section>
  </main>;
}

function AnswerForm({ id, item, advancing, onNext, onReload }: { id: string; item: AssessmentItem; advancing: boolean; onNext: () => Promise<void>; onReload: () => Promise<void> }) {
  const router = useRouter();
  const [choice, setChoice] = useState("");
  const [text, setText] = useState(item.draft_text ?? "");
  const [savedText, setSavedText] = useState(item.draft_text ?? "");
  const [revision, setRevision] = useState(item.revision);
  const [saving, setSaving] = useState(false);
  const [finalized, setFinalized] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const running = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const dirty = !finalized && (item.kind === "SHORT_WRITING" ? text !== savedText : !!choice);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty || saving) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, saving]);
  const save = async (finalize: boolean, exit = false) => {
    if (running.current || conflict || finalized) return;
    let answer: AssessmentAnswer;
    if (item.kind === "MULTIPLE_CHOICE") {
      if (!choice) return;
      answer = { kind: item.kind, selected_choice_id: choice, expected_revision: revision };
    } else if (item.kind === "SHORT_WRITING") {
      if (finalize && !text.trim()) return;
      answer = { kind: item.kind, text, finalize, expected_revision: revision };
    } else return; // Speaking has its own recorder/upload/save component.
    running.current = true; setSaving(true); setError(""); setMessage("");
    try {
      const result = await saveAssessmentAnswer(id, item.response_id, answer);
      setRevision(result.revision);
      if (result.status === "ASSIGNED") { setSavedText(text); setMessage("Draft saved."); }
      else { setFinalized(true); setMessage(result.status === "SKIPPED" ? "Speaking skipped and saved." : "Answer saved."); }
      if (exit) router.push("/");
      else if (result.status !== "ASSIGNED") await onNext();
    } catch (failure) {
      setError(requestError(failure));
      if (isAxiosError(failure) && failure.response?.status === 409) setConflict(true);
    } finally { running.current = false; setSaving(false); }
  };
  const disabled = saving || advancing || conflict || finalized;
  const exit = () => { if (!dirty || window.confirm("Leave without saving this answer?")) router.push("/"); };
  return <>
    <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold leading-relaxed outline-none whitespace-pre-wrap">{item.prompt}</h1>
    <p className="my-4 text-sm text-[#5a685f]">Final answers are saved before moving on and cannot be changed.</p>
    {item.kind === "MULTIPLE_CHOICE" && <fieldset disabled={disabled} className="mt-6 space-y-3"><legend className="mb-3 text-sm">Choose one answer.</legend>{item.choices?.map(option => <label key={option.id} className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 p-4 ${choice === option.id ? "border-brand-green bg-[#edf5ed]" : "border-[#dce4d7]"}`}><input type="radio" name={item.response_id} value={option.id} checked={choice === option.id} onChange={() => setChoice(option.id)} className="h-5 w-5 accent-[#1a6b45]" /><span>{option.text}</span></label>)}</fieldset>}
    {item.kind === "SHORT_WRITING" && <div className="mt-6"><label htmlFor="assessment-writing" className="mb-3 block font-medium">Your answer</label><textarea id="assessment-writing" value={text} disabled={saving || advancing || finalized} maxLength={10000} onChange={event => { setText(event.target.value); setMessage(""); }} spellCheck={false} autoCorrect="off" aria-describedby="writing-status" className="min-h-60 w-full rounded-xl border border-[#bbc8b9] p-4 leading-7" /><p id="writing-status" className="mt-2 text-sm text-[#5a685f]">{text.trim() ? text.trim().split(/\s+/u).length : 0} words · {text.length}/10,000 characters · {dirty ? "Unsaved changes" : "Matches saved draft"}</p><p className="mt-3 text-xs text-[#5a685f]">Use Save draft to preserve your original wording before leaving. Drafts are not saved automatically.</p></div>}
    {message && <p role="status" className="mt-5 text-brand-green">{message}</p>}
    {error && <p role="alert" className="mt-5 text-red-800">{error}</p>}
    {conflict && <div className="mt-4"><p className="text-sm leading-7">Your local answer is still visible. Copy any text you want to keep before reloading the saved version.</p><button className="journey-secondary mt-3" onClick={onReload}>Discard local changes & reload saved answer</button></div>}
    <div className="mt-8 flex flex-wrap gap-3">
      {finalized ? <button className="journey-primary" disabled={saving || advancing} onClick={onNext}>{advancing ? "Loading…" : "Continue to next activity"}</button> : <>
        {item.kind === "SHORT_WRITING" && <><button className="journey-secondary" disabled={disabled} onClick={() => save(false)}>Save draft</button><button className="journey-secondary" disabled={disabled} onClick={() => save(false, true)}>Save draft & exit</button></>}
        {(item.kind !== "RECORDED_SPEAKING" || item.optional) && <button className="journey-primary" disabled={disabled || (item.kind === "MULTIPLE_CHOICE" && !choice) || (item.kind === "SHORT_WRITING" && !text.trim())} onClick={() => save(true)}>{saving ? "Saving…" : item.kind === "RECORDED_SPEAKING" ? "Skip speaking" : item.kind === "SHORT_WRITING" ? "Finalize writing & continue" : "Save & continue"}</button>}
      </>}
      <button className="journey-secondary" disabled={saving || advancing} onClick={exit}>Exit</button>
    </div>
  </>;
}
