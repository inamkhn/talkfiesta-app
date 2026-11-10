"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { isAxiosError } from "axios";
import { useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";

function subscribe(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  window.addEventListener("popstate", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
    window.removeEventListener("popstate", onChange);
  };
}

function readToken() {
  // Match backend email links; never persist or log the action token.
  return new URLSearchParams(window.location.hash.slice(1)).get("token")
    ?? new URLSearchParams(window.location.search).get("token") ?? "";
}

function VerifyEmail({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const authenticated = useAuthStore(state => state.isAuthenticated);
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [error, setError] = useState("");
  const validLink = !!token && token.length <= 4096 && !invalid;

  async function verify() {
    if (inFlight.current || done || !validLink) return;
    inFlight.current = true;
    setPending(true);
    setError("");
    try {
      await authApi.verifyEmail({ token });
      setDone(true);
      // Re-read the signed-in account. The emailed token may belong to a
      // different account, so never set its verified timestamp optimistically.
      void queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    } catch (failure) {
      const response = isAxiosError(failure) ? failure.response : undefined;
      if (response?.status === 401 || response?.data?.code === "INVALID_ACTION_TOKEN") setInvalid(true);
      else if (response?.status === 429) setError("Too many attempts. Please wait before trying again.");
      else setError("We couldn’t confirm verification. Try again. If this link was already used, sign in to check your account or request a new link.");
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return <div className="space-y-6">
    <h2 className="text-3xl font-bold text-[#202d27]">Verify your email</h2>
    {done ? <>
      <p role="status" className="rounded-xl bg-emerald-50 p-4 text-emerald-900">The email address linked to this verification link is now verified.</p>
      <Link className="journey-primary inline-flex" href={authenticated ? "/onboarding" : "/login"}>{authenticated ? "Continue to your account" : "Sign in"}</Link>
    </> : !validLink ? <>
      <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">This link is missing, invalid, expired, or has already been used. You can request another link. If you already verified your email, continue to your account.</p>
      <Link className="journey-primary inline-flex" href="/request-email-verification">Request a new link</Link>
      <Link className="block py-3 text-brand-green underline" href={authenticated ? "/onboarding" : "/login"}>Continue to your account</Link>
    </> : <>
      <p className="leading-7 text-[#5a685f]">Confirm the email address for your TalkFiesta account. This link can only be used once.</p>
      {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}
      <Button onClick={verify} isLoading={pending} className="w-full">Verify email</Button>
      {!pending && <Link className="inline-flex min-h-11 items-center text-brand-green underline" href="/request-email-verification">Request a new verification link</Link>}
    </>}
  </div>;
}

export default function VerifyEmailPage() {
  const token = useSyncExternalStore(subscribe, readToken, () => null);
  if (token === null) return <p role="status">Loading verification link…</p>;
  return <VerifyEmail key={token} token={token} />;
}
