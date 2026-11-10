"use client";
import Link from "next/link";
import { BookOpen, Mic, PenLine } from "lucide-react";
import { MotionConfig } from "framer-motion";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user"><div className="journey-theme min-h-screen px-5 py-8 sm:px-8">
    <header className="mx-auto max-w-6xl"><Link href="/" className="inline-flex min-h-11 items-center text-2xl font-bold tracking-tight text-brand-green">TalkFiesta<span className="text-brand-orange">.</span></Link></header>
    <main className="mx-auto grid max-w-6xl items-center gap-10 py-10 lg:grid-cols-2 lg:gap-20 lg:py-16">
      <aside className="hidden lg:block"><p className="journey-eyebrow">ONE DAY AT A TIME</p><h1 className="journey-heading !text-5xl">A little practice.<br />A more confident you.</h1><p className="mt-6 max-w-md leading-7 text-[#5a685f]">Make English part of your everyday life, with practice that starts from your goals.</p><div className="mt-10 space-y-4">{[{ Icon: Mic, title: "Speak with purpose", body: "Practice for conversations that matter to you." }, { Icon: BookOpen, title: "Find the right words", body: "Build vocabulary in everyday contexts." }, { Icon: PenLine, title: "Express yourself clearly", body: "Turn small writing tasks into a steady habit." }].map(({ Icon, title, body }) => { return <div key={title} className="flex items-start gap-4 rounded-2xl border border-[#e0e5db] bg-white p-5"><span className="rounded-xl bg-[#edf2e9] p-3 text-brand-green"><Icon size={20} aria-hidden="true" /></span><div><h2 className="font-semibold">{title}</h2><p className="mt-1 text-sm leading-6 text-[#5a685f]">{body}</p></div></div>; })}</div></aside>
      <div className="auth-card mx-auto w-full max-w-md rounded-3xl border border-[#dce4d7] bg-white p-6 shadow-sm sm:p-9">{children}</div>
    </main><p className="text-center text-xs text-[#5a685f]">Speaking · Vocabulary · Writing</p>
  </div></MotionConfig>;
}
