"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { Menu, X } from "lucide-react";
const links = [["/#how-it-works", "How It Works"], ["/#features", "Learning Skills"], ["/#pricing", "Pricing"], ["/#faq", "FAQs"]];
export function Header() {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  return <header className="sticky top-0 z-50 border-b border-[#e0e5db] bg-[#faf9f6]/95 backdrop-blur-md" onKeyDown={(e) => { if (e.key === "Escape" && open) { setOpen(false); toggle.current?.focus(); } }}>
    <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:p-4">Skip to content</a>
    <div className="mx-auto flex min-h-20 max-w-7xl items-center justify-between gap-3 px-5 sm:px-8">
      <Link href="/" aria-label="TalkFiesta home" className="flex min-h-11 items-center gap-2 text-xl font-bold tracking-tight text-brand-green"><span aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-green text-base text-white">tf.</span>TalkFiesta<span aria-hidden="true" className="text-brand-orange">.</span></Link>
      <nav aria-label="Main navigation" className="hidden items-center gap-6 text-sm font-medium lg:flex">{links.map(([href, label]) => <Link key={href} href={href} className="py-3 text-[#5a685f] hover:text-brand-green">{label}</Link>)}</nav>
      <div className="flex items-center gap-3"><Link href="/login" className="hidden min-h-11 items-center px-3 text-sm font-semibold text-brand-green sm:inline-flex">Log In</Link><Link href="/register" className="journey-primary !px-4 !text-sm">Sign Up</Link><button ref={toggle} type="button" className="flex h-11 w-11 items-center justify-center rounded-lg border border-[#d5dfd3] lg:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>{open ? <X size={20} /> : <Menu size={20} />}</button></div>
    </div>
    {open && <nav id="mobile-nav" aria-label="Mobile navigation" className="border-t border-[#e0e5db] px-5 py-4 lg:hidden">{[...links, ["/login", "Log In"], ["/register", "Sign Up"]].map(([href, label]) => <Link key={href} href={href} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-3 text-sm font-medium hover:bg-[#edf2e9]">{label}</Link>)}</nav>}
  </header>;
}
