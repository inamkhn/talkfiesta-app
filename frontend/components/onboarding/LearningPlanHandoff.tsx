"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { cefrNames, getPlanHandoff } from "@/lib/api/assessment-result";

const goalNames = { FLUENCY: "Everyday fluency", BUSINESS: "Business English", EXAM: "Exam preparation", TRAVEL: "Travel English" };
const skillNames = { SPEAKING: "Speaking", VOCABULARY: "Vocabulary", WRITING: "Writing" };
export function LearningPlanHandoff() {
  const userId = useAuthStore(store => store.user?.id);
  const handoff = useQuery({ queryKey: ["learning-plan-handoff", userId], queryFn: ({ signal }) => getPlanHandoff(signal), retry: false, staleTime: 0 });
  if (handoff.isPending) return <p role="status" className="p-12 text-center">Loading your learning plan…</p>;
  if (!handoff.data) return <main className="mx-auto max-w-2xl px-5 py-12"><h1 className="journey-heading">Your plan preview couldn’t be loaded.</h1><p role="alert" className="mt-5 leading-7 text-[#5a685f]">Your completed onboarding and assessment result are saved. Retry to load the existing plan.</p><div className="mt-7 flex flex-wrap gap-3"><button className="journey-primary" disabled={handoff.isFetching} onClick={() => handoff.refetch()}>Reload plan</button><Link href="/dashboard" className="journey-secondary">Go to my dashboard</Link></div></main>;
  const { plan, modules, activities } = handoff.data;
  return <main className="mx-auto max-w-4xl px-5 py-12">
    {handoff.isError && <p role="alert" className="mb-5 rounded-xl bg-orange-50 p-4">We couldn’t refresh the plan. The last confirmed preview is shown. <button className="underline" onClick={() => handoff.refetch()}>Retry</button></p>}
    <p className="journey-eyebrow">YOUR LEARNING PLAN · CYCLE {plan.cycle}</p>
    <h1 className="journey-heading">Your next 21 days start here.</h1>
    <p className="mt-5 max-w-2xl leading-7 text-[#5a685f]">Your modules advance independently, so you can focus on one or all three. A 21-day cycle gives your practice structure; progress develops at your own pace.</p>
    <dl className="my-8 grid gap-4 rounded-2xl border border-[#dce4d7] bg-white p-6 sm:grid-cols-2">
      <div><dt className="text-sm text-[#5a685f]">Provisional starting level</dt><dd className="mt-2 font-semibold text-brand-green">{plan.placement_cefr} — {cefrNames[plan.placement_cefr]}</dd></div>
      <div><dt className="text-sm text-[#5a685f]">Daily practice goal</dt><dd className="mt-2 font-semibold">{plan.daily_target_minutes} minutes</dd></div>
      <div><dt className="text-sm text-[#5a685f]">Your goals</dt><dd className="mt-2 font-semibold">{plan.goals.map(goal => goalNames[goal]).join(", ")}</dd></div>
      <div><dt className="text-sm text-[#5a685f]">Focus skills</dt><dd className="mt-2 font-semibold">{plan.focus_areas.map(skill => skillNames[skill]).join(", ")}</dd></div>
    </dl>
    <h2 className="text-2xl font-semibold">Your current activities</h2>
    <div className="mt-5 grid gap-4 md:grid-cols-3">{modules.map(module => {
      const activity = activities.find(item => item.module === module.module);
      return <article key={module.module} className="rounded-2xl border border-[#dce4d7] bg-white p-6"><p className="journey-eyebrow">{skillNames[module.module]} · DAY {activity?.day ?? module.current_day}</p><h3 className="mt-4 text-xl font-semibold">{activity?.title ?? (module.status === "COMPLETED" ? "Cycle completed" : "Activity content is not available yet")}</h3>{activity?.description && <p className="mt-3 text-sm leading-7 text-[#5a685f]">{activity.description}</p>}{activity?.estimated_minutes && <p className="mt-4 text-sm text-[#5a685f]">About {activity.estimated_minutes} minutes</p>}<p className="mt-4 text-sm font-medium text-brand-green">{module.status === "COMPLETED" || activity?.activity_status === "COMPLETED" ? "Completed" : activity?.activity_status === "IN_PROGRESS" ? "In progress" : module.status === "AWAITING_CONTENT" || !activity?.title ? "Awaiting content" : "Ready to practice"}</p>{module.prioritized && <p className="mt-2 text-xs text-[#5a685f]">One of your focus skills</p>}</article>;
    })}</div>
    <Link className="journey-primary mt-9" href="/dashboard">Go to my dashboard</Link>
  </main>;
}
