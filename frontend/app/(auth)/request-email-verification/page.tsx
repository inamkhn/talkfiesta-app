"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { isAxiosError } from "axios";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function RequestVerification({ initialEmail, authenticated }: { initialEmail: string; authenticated: boolean }) {
  const [email, setEmail] = useState(initialEmail);
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError("");
    setSent(false);
    try {
      await authApi.requestEmailVerification({ email: email.trim() });
      setSent(true);
    } catch (failure) {
      const status = isAxiosError(failure) ? failure.response?.status : undefined;
      setError(status === 429 ? "Too many requests. Please wait before requesting another link."
        : status === 422 ? "Enter a valid email address."
        : "We couldn’t request a verification email. Please try again later.");
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return <div className="space-y-6">
    <h2 className="text-3xl font-bold text-[#202d27]">Confirm your email address</h2>
    <p className="leading-7 text-[#5a685f]">Request a verification link for your TalkFiesta account.</p>
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="verification-email">Email address</Label>
        <Input id="verification-email" type="email" autoComplete="email" required maxLength={254} disabled={pending} value={email} onChange={event => { setEmail(event.target.value); setSent(false); setError(""); }} />
      </div>
      {sent && <p role="status" className="rounded-xl bg-emerald-50 p-4 text-sm leading-6 text-emerald-900">If this account is eligible, a verification link will be sent. Check your inbox and spam folder. Already verified accounts do not receive another email.</p>}
      {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      <Button type="submit" isLoading={pending} className="w-full">{sent ? "Request another link" : "Send verification link"}</Button>
    </form>
    <Link className="inline-flex min-h-11 items-center text-brand-green underline" href={authenticated ? "/onboarding" : "/login"}>{authenticated ? "Continue to your account" : "Back to sign in"}</Link>
  </div>;
}

export default function RequestVerificationPage() {
  const user = useAuthStore(state => state.user);
  return <RequestVerification key={user?.id ?? "guest"} initialEmail={user?.email ?? ""} authenticated={!!user} />;
}
