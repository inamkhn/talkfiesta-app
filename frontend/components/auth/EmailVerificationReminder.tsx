"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/authStore";

export function EmailVerificationReminder() {
  const user = useAuthStore(state => state.user);
  if (!user || user.email_verified_at) return null;
  return <aside aria-label="Email verification reminder" className="journey-theme border-b border-[#dce4d7] bg-[#edf2e9] px-5 py-3 text-center text-sm leading-6">
    Your email address hasn’t been verified yet. You can keep learning. {" "}
    <Link className="inline-flex min-h-11 items-center font-semibold text-brand-green underline" href="/request-email-verification">Send a verification link</Link>
  </aside>;
}
