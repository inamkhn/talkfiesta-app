"use client";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { mountGoogleButton } from "@/lib/google-sign-in";

type Props = { onCredential: (token: string) => void; disabled: boolean; pending: boolean };
const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();
export function GoogleSignIn({ onCredential, disabled, pending }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const blocked = useRef(disabled);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { callback.current = onCredential; blocked.current = disabled; }, [onCredential, disabled]);
  useEffect(() => {
    if (!ready || !clientId || !container.current) return;
    let cleanup: (() => void) | undefined;
    let mounted = true;
    // Defer until the DOM is mounted, including React's development remount.
    queueMicrotask(() => {
      if (!mounted || !container.current) return;
      try {
        cleanup = mountGoogleButton(container.current, clientId, token => {
          if (!mounted || blocked.current) return;
          if (!token || token.length > 8192) { setError("Google didn’t provide a valid sign-in response. Please try again."); return; }
          setError("");
          callback.current(token);
        });
      } catch { setError("Google sign-in couldn’t load. Continue with email or reload this page."); }
    });
    return () => { mounted = false; cleanup?.(); };
  }, [ready]);
  if (!clientId) return <p className="text-center text-sm leading-6 text-[#5a685f]">Google sign-in is currently unavailable. Please continue with email.</p>;
  return <div aria-busy={pending}>
    <Script id="google-identity-services" src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={() => setReady(true)} onError={() => setError("Google sign-in couldn’t load. Check your connection or continue with email.")} />
    {!ready && !error && <p role="status" className="text-center text-sm text-[#5a685f]">Loading Google sign-in…</p>}
    <div ref={container} inert={disabled} className={disabled ? "pointer-events-none min-h-11 opacity-50" : "min-h-11"} />
    {pending && <p role="status" className="mt-3 text-center text-sm text-brand-green">Signing in with Google…</p>}
    {error && <div role="alert" className="mt-3 text-sm text-red-800"><p>{error}</p><button type="button" className="mt-2 min-h-11 underline" onClick={() => window.location.reload()}>Reload Google sign-in</button></div>}
    <p className="mt-3 text-center text-xs leading-6 text-[#5a685f]">If the Google window is blocked or closed, you can try again or use email above.</p>
  </div>;
}
