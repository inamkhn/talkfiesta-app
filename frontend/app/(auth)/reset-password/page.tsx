"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { useAuth } from "@/hooks/useAuth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const resetSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type ResetFormValues = z.infer<typeof resetSchema>;

function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const [serverError, setServerError] = useState<string | null>(null);
  const [isDone, setIsDone] = useState(false);
  const { resetPassword, isResettingPassword } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetFormValues>({
    resolver: zodResolver(resetSchema),
  });

  const onSubmit = (data: ResetFormValues) => {
    setServerError(null);
    resetPassword(
      { token, new_password: data.password },
      {
        onSuccess: () => setIsDone(true),
        onError: (error: any) => {
          const detail = error?.response?.data?.detail;
          if (Array.isArray(detail)) {
            setServerError(detail[0]?.msg || "Reset failed");
          } else if (typeof detail === "string") {
            setServerError(detail);
          } else {
            setServerError("An unexpected error occurred. Please try again.");
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
        <h2 className="mt-8 text-3xl font-bold tracking-tight text-white">
          Choose a new password
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          This signs you out everywhere so nothing keeps the old password alive.
        </p>
      </div>

      <div className="mt-10">
        {!token ? (
          <div className="space-y-6">
            <div className="p-4 text-sm bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg">
              This link is missing its token. Reset links expire after a short
              while, so request a fresh one.
            </div>
            <Link
              href="/forgot-password"
              className="block w-full text-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
            >
              Request a new link
            </Link>
          </div>
        ) : isDone ? (
          <div className="space-y-6">
            <div className="p-4 text-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded-lg">
              Password updated. You can sign in with your new password.
            </div>
            <Link
              href="/login"
              className="block w-full text-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
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
                type="password"
                autoComplete="new-password"
                {...register("password")}
                className={errors.password ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {errors.password && (
                <p className="text-xs text-red-400 mt-1">{errors.password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm new password</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                {...register("confirmPassword")}
                className={
                  errors.confirmPassword ? "border-red-500 focus-visible:ring-red-500" : ""
                }
              />
              {errors.confirmPassword && (
                <p className="text-xs text-red-400 mt-1">
                  {errors.confirmPassword.message}
                </p>
              )}
            </div>

            {serverError && (
              <div className="p-3 text-sm bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg">
                {serverError}
              </div>
            )}

            <div>
              <Button type="submit" className="w-full" isLoading={isResettingPassword}>
                Update password
              </Button>
            </div>
          </form>
        )}
      </div>
    </motion.div>
  );
}

export default function ResetPasswordPage() {
  // useSearchParams needs a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
