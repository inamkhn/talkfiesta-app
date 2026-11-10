"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { isAxiosError } from "axios";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { useAuth } from "@/hooks/useAuth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const resetSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters").max(128, "Password must be at most 128 characters"),
    confirmPassword: z.string(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type ResetFormValues = z.infer<typeof resetSchema>;

function ResetPasswordForm({ token }: { token: string }) {
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [invalidLink, setInvalidLink] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const { resetPassword, isResettingPassword } = useAuth();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ResetFormValues>({
    resolver: zodResolver(resetSchema),
  });

  const onSubmit = (data: ResetFormValues) => {
    if (isResettingPassword || !token || token.length > 4096 || invalidLink) return;
    setServerError(null);
    resetPassword(
      { token, new_password: data.password },
      {
        onSuccess: () => { reset(); setIsDone(true); },
        onError: (error: unknown) => {
          const problem = isAxiosError<{ code?: string; detail?: string }>(error) ? error.response : undefined;
          if (problem?.data.code === "INVALID_ACTION_TOKEN" || problem?.status === 401) {
            reset();
            setInvalidLink(true);
          } else if (problem?.status === 429) {
            setServerError("Too many attempts. Please wait and try again.");
          } else if (problem?.status === 422) {
            setServerError(problem.data.detail || "Check your password and try again.");
          } else {
            setServerError("We couldn’t confirm the password reset. Try again, or request a new link if this one has already been used.");
          }
        },
      }
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="text-center sm:text-left">
        <h2 className="mt-8 text-3xl font-bold tracking-tight text-[#202d27]">
          Choose a new password
        </h2>
        <p className="mt-2 text-sm text-[#5a685f]">
          Choose 8–128 characters. After resetting, sign in again with your new password.
        </p>
      </div>

      <div className="mt-10">
        {!token || token.length > 4096 || invalidLink ? (
          <div className="space-y-6">
            <div role="alert" className="p-4 text-sm bg-red-500/10 border border-red-500/20 text-red-700 rounded-lg">
              This reset link is missing, invalid, expired, or has already been used. Request a new link to continue.
            </div>
            <Link
              href="/forgot-password"
              className="block w-full text-center rounded-lg bg-brand-green px-4 py-2.5 text-sm font-medium text-white hover:bg-[#145436] transition-colors"
            >
              Request a new link
            </Link>
          </div>
        ) : isDone ? (
          <div className="space-y-6">
            <div role="status" className="p-4 text-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-800 rounded-lg">
              Password updated. You can sign in with your new password.
            </div>
            <Link
              href="/login"
              replace
              className="block w-full text-center rounded-lg bg-brand-green px-4 py-2.5 text-sm font-medium text-white hover:bg-[#145436] transition-colors"
            >
              Go to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="password">New password</Label>
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                disabled={isResettingPassword}
                {...register("password")}
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? "password-error" : undefined}
                className={errors.password ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {errors.password && (
                <p id="password-error" role="alert" className="text-xs text-red-700 mt-1">{errors.password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm new password</Label>
              <Input
                id="confirmPassword"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                disabled={isResettingPassword}
                {...register("confirmPassword")}
              aria-invalid={!!errors.confirmPassword}
              aria-describedby={errors.confirmPassword ? "confirmPassword-error" : undefined}
                className={
                  errors.confirmPassword ? "border-red-500 focus-visible:ring-red-500" : ""
                }
              />
              {errors.confirmPassword && (
                <p id="confirmPassword-error" role="alert" className="text-xs text-red-700 mt-1">
                  {errors.confirmPassword.message}
                </p>
              )}
            </div>

<label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm"><input type="checkbox" className="!h-4 !w-4 accent-[#1a6b45]" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />Show password</label>
            {serverError && (
              <div role="alert" className="p-3 text-sm bg-red-500/10 border border-red-500/20 text-red-700 rounded-lg">
                {serverError}
              </div>
            )}

            <div>
              <Button type="submit" className="w-full" isLoading={isResettingPassword}>
                Update password
              </Button>
            </div>
            <Link href="/forgot-password" className="inline-flex min-h-11 items-center text-sm font-medium text-brand-green hover:underline">Request a new reset link</Link>
          </form>
        )}
      </div>
    </motion.div>
  );
}

function subscribeToLink(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  window.addEventListener("popstate", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
    window.removeEventListener("popstate", onChange);
  };
}

function readResetToken(): string {
  // Backend emails use fragments to keep the token out of server request logs.
  // Accept older query-string links as well; never log or persist either token.
  return new URLSearchParams(window.location.hash.slice(1)).get("token")
    ?? new URLSearchParams(window.location.search).get("token")
    ?? "";
}

export default function ResetPasswordPage() {
  const token = useSyncExternalStore(subscribeToLink, readResetToken, () => null);
  if (token === null) return <p role="status" className="py-8 text-[#5a685f]">Loading reset link…</p>;
  // A different link must discard the previous token's success/error state.
  return <ResetPasswordForm key={token} token={token} />;
}
