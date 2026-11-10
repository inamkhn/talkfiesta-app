"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import apiClient from "@/lib/api/axios";

type Preferences = { goals: string[]; focus_areas: string[]; topics: string[]; daily_minutes: number; self_reported_comfort: string };
const goalOptions = [["BUSINESS", "Business & professional English", "Meetings, interviews, and workplace communication."], ["FLUENCY", "Everyday fluency", "Conversations and everyday situations."], ["TRAVEL", "Travel & social communication", "New places, new people, new experiences."], ["EXAM", "Exam preparation", "Structured practice, without official exam scoring."]];
const focusOptions = [["SPEAKING", "Speaking"], ["VOCABULARY", "Vocabulary"], ["WRITING", "Writing & grammar"]];
const topicOptions = [["DAILY_LIFE", "Daily life"], ["WORK", "Work"], ["TRAVEL", "Travel"], ["TECHNOLOGY", "Technology"], ["CULTURE", "Culture"], ["EDUCATION", "Education"], ["HEALTH", "Health"], ["HOBBIES", "Hobbies"]];

export function OnboardingWizard() {
  const profile = useQuery({ queryKey: ["onboarding-preferences"], queryFn: async () => (await apiClient.get<{ preferences: Partial<Preferences> }>("/users/me")).data, retry: false });
  if (profile.isPending) return <p role="status" className="py-16 text-center text-[#5a685f]">Loading your saved preferences…</p>;
  if (profile.isError) return <div className="rounded-2xl border border-[#e0e5db] bg-white p-8"><h1 className="text-2xl font-semibold">Let’s get your setup ready.</h1><p role="alert" className="my-5 text-[#5a685f]">We couldn’t load your preferences. Please try again before making changes.</p><button className="journey-primary" onClick={() => profile.refetch()}>Try again</button></div>;
  return <PreferencesForm saved={profile.data.preferences} />;
}
function PreferencesForm({ saved }: { saved: Partial<Preferences> }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const heading = useRef<HTMLHeadingElement>(null);
  const [step, setStep] = useState(1);
  const [preferences, setPreferences] = useState<Preferences>({ goals: saved.goals ?? [], focus_areas: saved.focus_areas ?? [], topics: saved.topics ?? [], daily_minutes: saved.daily_minutes ?? 15, self_reported_comfort: saved.self_reported_comfort ?? "SIMPLE" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const toggle = (field: "goals" | "focus_areas" | "topics", value: string) => setPreferences(previous => ({ ...previous, [field]: previous[field].includes(value) ? previous[field].filter(item => item !== value) : [...previous[field], value] }));
  const changeStep = (value: number) => { setError(""); setStep(value); requestAnimationFrame(() => heading.current?.focus()); };
  const save = async () => {
    if (busy.current) return;
    if (!preferences.focus_areas.length) { setError("Choose at least one focus skill."); return; }
    busy.current = true; setSaving(true); setError("");
    try {
      await apiClient.put("/onboarding/preferences", { ...preferences, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" });
      await queryClient.invalidateQueries({ queryKey: ["onboarding-preferences"] });
      await queryClient.invalidateQueries({ queryKey: ["onboarding-state"] });
      router.replace("/onboarding");
    } catch { setError("We couldn’t save your preferences. Your selections are still here. Please try again."); }
    finally { busy.current = false; setSaving(false); }
  };
  return <>
    <ol aria-label="Setup progress" className="mb-10 flex gap-5 text-sm">{["Goals", "Preferences"].map((label, i) => <li key={label} aria-current={step === i + 1 ? "step" : undefined} className={`flex flex-1 items-center gap-3 border-b-2 pb-4 ${step >= i + 1 ? "border-brand-green text-brand-green" : "border-[#dce4d7] text-[#5a685f]"}`}><span className="flex h-7 w-7 items-center justify-center rounded-full border text-xs">{step > i + 1 ? <Check size={15} aria-hidden="true" /> : i + 1}</span>{label}</li>)}</ol>
    <h1 ref={heading} tabIndex={-1} className="journey-heading outline-none">{step === 1 ? "What would you like to achieve in English?" : "Let’s make your plan fit your life."}</h1>
    <p className="mb-8 mt-4 leading-7 text-[#5a685f]">{step === 1 ? "Choose everything that matters to you. You can change this later." : "Choose a focus, a little time, and topics you enjoy. Your level check comes next."}</p>
    <form onSubmit={event => { event.preventDefault(); if (step === 1) { if (!preferences.goals.length) setError("Choose at least one goal to continue."); else changeStep(2); } else void save(); }}>
      <fieldset disabled={saving} className="space-y-8">
        {step === 1 ? <fieldset><legend className="sr-only">Your learning goals — choose at least one</legend><div className="grid gap-4 sm:grid-cols-2">{goalOptions.map(([value, title, description]) => <label key={value} className={`flex cursor-pointer items-start gap-3 rounded-2xl border-2 p-5 ${preferences.goals.includes(value) ? "border-brand-green bg-[#edf5ed]" : "border-[#e0e5db] bg-white"}`}><input type="checkbox" checked={preferences.goals.includes(value)} onChange={() => toggle("goals", value)} className="mt-1 h-5 w-5 shrink-0 accent-[#1a6b45]" /><span><span className="block font-semibold">{title}</span><span className="mt-2 block text-sm leading-6 text-[#5a685f]">{description}</span></span></label>)}</div></fieldset> : <>
          <Choices legend="What would you like to focus on?" options={focusOptions} selected={preferences.focus_areas} onToggle={value => toggle("focus_areas", value)} />
          <fieldset><legend className="mb-3 font-semibold">Your daily practice time</legend><div className="flex flex-wrap gap-3">{[5, 10, 15, 20, 30, 45, 60].map(minutes => <label key={minutes} className={`flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border px-4 ${preferences.daily_minutes === minutes ? "border-brand-green bg-[#edf5ed]" : "border-[#dce4d7] bg-white"}`}><input type="radio" name="minutes" checked={preferences.daily_minutes === minutes} onChange={() => setPreferences({ ...preferences, daily_minutes: minutes })} className="accent-[#1a6b45]" />{minutes} min</label>)}</div></fieldset>
          <Choices legend="Topics you enjoy (optional)" options={topicOptions} selected={preferences.topics} onToggle={value => toggle("topics", value)} />
          <div><label htmlFor="comfort" className="mb-3 block font-semibold">How comfortable do you feel speaking?</label><select id="comfort" value={preferences.self_reported_comfort} onChange={event => setPreferences({ ...preferences, self_reported_comfort: event.target.value })} className="min-h-12 w-full rounded-xl border border-[#bbc8b9] bg-white px-4"><option value="BEGINNER">I’m just starting</option><option value="SIMPLE">I can manage simple conversations</option><option value="COMFORTABLE">I can talk about familiar topics confidently</option><option value="CONFIDENT">I feel comfortable discussing complex topics</option></select><p className="mt-3 text-sm leading-6 text-[#5a685f]">This helps us choose a starting point. It isn’t a verified English level.</p></div>
        </>}
      </fieldset>
      {error && <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      <div className="mt-10 flex flex-wrap justify-between gap-3 border-t border-[#dce4d7] pt-6">{step === 2 ? <button type="button" disabled={saving} onClick={() => changeStep(1)} className="journey-secondary"><ArrowLeft size={16} aria-hidden="true" />Back</button> : <p className="self-center text-xs text-[#5a685f]">Step 1 of 2 · Choose one or more</p>}<button type="submit" disabled={saving} aria-busy={saving} className="journey-primary">{saving ? "Saving preferences…" : step === 1 ? "Continue" : "Save & Continue to Level Check"}<ArrowRight size={16} aria-hidden="true" /></button></div>
    </form>
  </>;
}
function Choices({ legend, options, selected, onToggle }: { legend: string; options: string[][]; selected: string[]; onToggle: (value: string) => void }) {
  return <fieldset><legend className="mb-3 font-semibold">{legend}</legend><div className="flex flex-wrap gap-3">{options.map(([value, label]) => <label key={value} className={`flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border px-4 ${selected.includes(value) ? "border-brand-green bg-[#edf5ed]" : "border-[#dce4d7] bg-white"}`}><input type="checkbox" checked={selected.includes(value)} onChange={() => onToggle(value)} className="accent-[#1a6b45]" />{label}</label>)}</div></fieldset>;
}
