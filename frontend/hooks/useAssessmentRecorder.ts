"use client";
import { useEffect, useRef, useState } from "react";

const MAX_BYTES = 10 * 1024 * 1024;
const MAX_SECONDS = 175; // Stay below the backend's default 180-second boundary.
const FORMATS = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
export function useAssessmentRecorder() {
  const [status, setStatus] = useState<"ready" | "permission" | "recording" | "stopping" | "recorded">("ready");
  const [clip, setClip] = useState<{ blob: Blob; url: string } | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [skipReason, setSkipReason] = useState<"DECLINED" | "MIC_UNAVAILABLE" | "TECHNICAL_ISSUE">("DECLINED");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const objectUrl = useRef<string | null>(null);
  const generation = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const requesting = useRef(false);
  const stop = () => {
    if (requesting.current) {
      generation.current += 1;
      requesting.current = false;
      setStatus("ready");
    }
    if (recorder.current?.state === "recording") { setStatus("stopping"); recorder.current.stop(); }
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };
  useEffect(() => {
    const stopWhenHidden = () => {
      if (document.hidden) {
        // Invalidates a still-pending permission request as well.
        generation.current += 1;
        requesting.current = false;
        if (recorder.current?.state === "recording") recorder.current.stop();
        stream.current?.getTracks().forEach(track => track.stop());
        if (timer.current) clearInterval(timer.current);
        setStatus(previous => previous === "permission" ? "ready" : previous);
      }
    };
    document.addEventListener("visibilitychange", stopWhenHidden);
    return () => {
      generation.current += 1;
      document.removeEventListener("visibilitychange", stopWhenHidden);
      if (timer.current) clearInterval(timer.current);
      if (recorder.current) { recorder.current.onstop = null; recorder.current.ondataavailable = null; recorder.current.onerror = null; if (recorder.current.state !== "inactive") recorder.current.stop(); }
      stream.current?.getTracks().forEach(track => track.stop());
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    };
  }, []);
  const start = async () => {
    if (requesting.current || recorder.current?.state === "recording") return;
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser cannot record audio here. Use a supported browser over HTTPS, or skip speaking."); setSkipReason("MIC_UNAVAILABLE"); return;
    }
    const mimeType = FORMATS.find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) { setError("This browser has no supported audio recording format. You can skip speaking."); setSkipReason("TECHNICAL_ISSUE"); return; }
    const version = ++generation.current;
    requesting.current = true; setStatus("permission");
    let granted: MediaStream | null = null;
    try {
      granted = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      if (generation.current !== version || document.hidden) { granted.getTracks().forEach(track => track.stop()); return; }
      stream.current = granted;
      const active = new MediaRecorder(granted, { mimeType, audioBitsPerSecond: 64000 });
      recorder.current = active;
      const chunks: Blob[] = [];
      let size = 0;
      let failed = false;
      const started = performance.now();
      active.ondataavailable = event => {
        if (event.data.size) { chunks.push(event.data); size += event.data.size; }
        if (size > MAX_BYTES) { failed = true; setError("The recording is too large. Please make a shorter recording."); stop(); }
      };
      active.onerror = () => { failed = true; setError("Recording was interrupted. Please try again or skip speaking."); setSkipReason("TECHNICAL_ISSUE"); stop(); };
      active.onstop = () => {
        granted?.getTracks().forEach(track => track.stop());
        if (timer.current) clearInterval(timer.current);
        recorder.current = null;
        const blob = new Blob(chunks, { type: active.mimeType.split(";")[0] });
        if (failed || blob.size === 0 || blob.size > MAX_BYTES || performance.now() - started < 1000) {
          setStatus("ready"); if (!failed) setError("Please record at least one second of audio before stopping."); return;
        }
        if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
        objectUrl.current = URL.createObjectURL(blob);
        setClip({ blob, url: objectUrl.current }); setStatus("recorded");
      };
      active.start(250);
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null; setClip(null); setSeconds(0); setSkipReason("DECLINED"); setStatus("recording");
      timer.current = setInterval(() => {
        const elapsed = Math.floor((performance.now() - started) / 1000);
        setSeconds(elapsed);
        if (elapsed >= MAX_SECONDS) stop();
      }, 250);
    } catch (failure) {
      granted?.getTracks().forEach(track => track.stop());
      if (generation.current !== version) return;
      const name = failure instanceof DOMException ? failure.name : "";
      setSkipReason(["NotAllowedError", "NotFoundError"].includes(name) ? "MIC_UNAVAILABLE" : "TECHNICAL_ISSUE");
      setError(name === "NotAllowedError" ? "Microphone permission was denied. Allow it in your browser and try again, or skip speaking." : name === "NotFoundError" ? "No microphone was found. Connect one or skip speaking." : "We couldn’t start recording. Check your microphone and try again.");
      setStatus("ready");
    } finally { if (generation.current === version) requesting.current = false; }
  };
  return { status, clip, seconds, error, skipReason, start, stop };
}
