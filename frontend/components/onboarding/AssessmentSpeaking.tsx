"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { isAxiosError } from "axios";
import { useAssessmentRecorder } from "@/hooks/useAssessmentRecorder";
import { AssessmentAnswer, AssessmentItem, saveAssessmentAnswer } from "@/lib/api/assessment";
import { allocateAssessmentAudio, AudioTicket, confirmAssessmentAudio } from "@/lib/api/assessment-audio";

type Upload = { blob: Blob; ticket: AudioTicket; transferred: boolean; verified: boolean };
export function AssessmentSpeaking({ id, item, advancing, onNext, onReload }: { id: string; item: AssessmentItem; advancing: boolean; onNext: () => Promise<void>; onReload: () => Promise<void> }) {
  const recorder = useAssessmentRecorder();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [saveStarted, setSaveStarted] = useState(false);
  const upload = useRef<Upload | null>(null);
  const pendingAnswer = useRef<AssessmentAnswer | null>(null);
  const operation = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const capturing = ["permission", "recording", "stopping"].includes(recorder.status);
  const locked = busy || advancing || saved || conflict;
  useEffect(() => {
    heading.current?.focus();
    return () => { operation.current?.abort(); };
  }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!saved && (recorder.clip || capturing || busy)) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [saved, recorder.clip, capturing, busy]);

  const save = async (skip: boolean) => {
    if (operation.current || saved || conflict || capturing || advancing) return;
    if (skip && !item.optional) return;
    if (!skip && !recorder.clip && !pendingAnswer.current) return;
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true); setError("");
    try {
      if (!pendingAnswer.current) {
        if (skip) {
          pendingAnswer.current = { kind: "RECORDED_SPEAKING", expected_revision: item.revision, skipped: true, skip_reason: recorder.skipReason };
        } else {
          const blob = recorder.clip!.blob;
          if (upload.current?.blob !== blob) upload.current = null;
          // A fresh allocation is safe before answer finalization. Older unbound
          // objects are handled by backend retention, never silently reused.
          if (upload.current && !upload.current.transferred && Date.parse(upload.current.ticket.expires_at) <= Date.now()) upload.current = null;
          if (!upload.current) {
            setPhase("Preparing audio upload…");
            const ticket = await allocateAssessmentAudio(item.response_id, blob, controller.signal);
            upload.current = { blob, ticket, transferred: false, verified: false };
          }
          const current = upload.current;
          if (!current.transferred) {
            setPhase("Uploading recording…");
            // The signed URL gets exactly the supplied headers and bytes, with
            // no application bearer token or browser cookies attached.
            const response = await fetch(current.ticket.upload_url, { method: current.ticket.method, headers: current.ticket.headers, body: blob, credentials: "omit", signal: controller.signal });
            // If the first PUT succeeded but its response was lost, the immutable
            // object already exists. Confirmation verifies checksum and binding.
            if (!response.ok && response.status !== 412) {
              if (response.status === 403) upload.current = null;
              throw new Error("The audio upload did not finish. Your recording is still here; try again.");
            }
            current.transferred = true;
          }
          if (!current.verified) {
            setPhase("Checking uploaded audio…");
            await confirmAssessmentAudio(current.ticket, item.response_id, controller.signal);
            current.verified = true;
          }
          pendingAnswer.current = { kind: "RECORDED_SPEAKING", expected_revision: item.revision, media_upload_id: current.ticket.upload_id };
        }
        setSaveStarted(true);
      }
      setPhase("Saving speaking answer…");
      // Retain this exact payload/revision after an uncertain response. Do not
      // allocate another upload or switch to skip before resolving the save.
      const result = await saveAssessmentAnswer(id, item.response_id, pendingAnswer.current, controller.signal);
      if (result.status === "ASSIGNED") throw new Error("The speaking answer was not finalized. Please retry saving.");
      setSaved(true);
      setPhase(result.status === "SKIPPED" ? "Speaking skipped and saved." : "Recording verified and answer saved.");
      await onNext();
    } catch (failure) {
      if (controller.signal.aborted) return;
      if (isAxiosError<{ code?: string; detail?: string }>(failure)) {
        const code = failure.response?.data?.code;
        if (["VERSION_CONFLICT", "ANSWER_FINALIZED", "ASSESSMENT_NOT_EDITABLE", "UPLOAD_NOT_BOUND"].includes(code ?? "")) {
          setConflict(true);
          setError("This response changed elsewhere. Your local recording remains available below. Reload the saved assessment before continuing.");
        } else {
          if (["UPLOAD_EXPIRED", "UPLOAD_NOT_CONFIRMABLE", "UPLOAD_NOT_FOUND"].includes(code ?? "") || failure.response?.status === 422) {
            // Do not discard the audio. Allow a new signed allocation on retry.
            if (!pendingAnswer.current) upload.current = null;
            // A definite validation rejection means this write did not commit.
            // It is safe to allocate again (for example after media retention).
            if (failure.response?.status === 422 && pendingAnswer.current && "media_upload_id" in pendingAnswer.current) {
              pendingAnswer.current = null;
              upload.current = null;
              setSaveStarted(false);
            }
          }
          setError(failure.response?.status === 429 ? "Too many requests. Please wait before trying again." : failure.response?.data?.detail || "We couldn’t confirm the save. Keep this page open and retry.");
        }
      } else setError(failure instanceof Error ? failure.message : "Upload interrupted. Your recording is still here; try again.");
      setPhase("");
    } finally {
      if (operation.current === controller) operation.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const exit = () => {
    if (saved || (!recorder.clip && !capturing) || window.confirm("This recording has not been saved as an answer. Leave and discard it?")) {
      recorder.stop(); router.push("/");
    }
  };
  return <>
    <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold leading-relaxed outline-none whitespace-pre-wrap">{item.prompt}</h1>
    <p className="mt-5 text-sm leading-7 text-[#5a685f]">Aim for 30–60 seconds. You can listen and record again before saving. {item.optional && "Speaking is optional; skipping marks it as not assessed."}</p>
    <details className="mt-4 rounded-xl border border-[#dce4d7] p-4"><summary className="cursor-pointer font-medium text-brand-green">How is my recording used?</summary><p className="mt-3 text-sm leading-7">Your browser requests microphone permission only when you start recording. Choosing “Use this recording” uploads the audio for assessment. Stopping, hiding this tab, or leaving releases the microphone. Recordings are limited to 2 minutes 55 seconds on this page.</p></details>
    <div className="mt-6 rounded-2xl bg-[#f3f5ef] p-6">
      {recorder.status === "recording" && <p className="mb-4 font-semibold" role="status">Recording · <span aria-live="off">{Math.floor(recorder.seconds / 60)}:{String(recorder.seconds % 60).padStart(2, "0")}</span></p>}
      {recorder.status === "permission" && <p role="status" className="mb-4">Allow microphone access in your browser. No audio is recorded until permission is granted.</p>}
      {recorder.status === "stopping" && <p role="status">Preparing playback…</p>}
      {recorder.clip && <div className="mb-5"><p id="recording-label" className="mb-3 font-medium">Your recording</p><audio controls src={recorder.clip.url} aria-labelledby="recording-label" className="w-full" preload="metadata" /><p className="mt-3 text-sm">{saved ? "Answer saved." : "Local preview — keep this page open until the answer is saved."}</p></div>}
      {recorder.status === "recording" ? <button className="journey-primary" onClick={recorder.stop}>Stop recording</button> : <button className="journey-secondary" disabled={locked || capturing || saveStarted} onClick={() => { setError(""); setPhase(""); void recorder.start(); }}>{recorder.clip ? "Record again" : "Start recording"}</button>}
      {recorder.status === "permission" && <p className="mt-3 text-sm">You can deny the browser prompt to return and skip speaking.</p>}
    </div>
    {recorder.error && <p role="alert" className="mt-5 text-red-800">{recorder.error}</p>}
    {phase && <p role="status" className="mt-5 text-brand-green">{phase}</p>}
    {error && <p role="alert" className="mt-5 text-red-800">{error}</p>}
    {conflict && <div className="mt-4"><p className="text-sm">Reloading discards this local recording. Download it first if you want to keep a copy.</p>{recorder.clip && <a href={recorder.clip.url} download={`assessment-recording.${recorder.clip.blob.type.split("/")[1]}`} className="journey-secondary mt-3">Download recording</a>}<button className="journey-secondary mt-3" onClick={onReload}>Discard local recording & reload</button></div>}
    <div className="mt-7 flex flex-wrap gap-3">
      {saved ? <button className="journey-primary" disabled={advancing || busy} onClick={onNext}>{advancing ? "Loading…" : "Continue"}</button> : <>
        {(recorder.clip || saveStarted) && <button className="journey-primary" disabled={locked || capturing} onClick={() => save(false)}>{busy ? "Saving…" : saveStarted ? "Retry saving answer" : "Use this recording"}</button>}
        {item.optional && <button className="journey-secondary" disabled={locked || capturing || saveStarted} onClick={() => save(true)}>Skip speaking</button>}
      </>}
      <button className="journey-secondary" disabled={busy || advancing} onClick={exit}>Exit</button>
    </div>
  </>;
}
