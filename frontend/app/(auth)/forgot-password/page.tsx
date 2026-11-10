"use client";

import { useState } from "react";
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

const forgotSchema = z.object({
  email: z.string().trim().email("Please enter a valid email"),
});

type ForgotFormValues = z.infer<typeof forgotSchema>;

export default function ForgotPasswordPage() {
  const [serverError, setServerError] = useState<string | null>(null);
  const [acknowledgement, setAcknowledgement] = useState<string | null>(null);
  const { requestPasswordReset, isRequestingReset } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotFormValues>({
    resolver: zodResolver(forgotSchema),
  });

  const onSubmit = (data: ForgotFormValues) => {
    if (isRequestingReset) return;
    setServerError(null);
    requestPasswordReset(data.email, {
      onSuccess: (response) => setAcknowledgement(response.message),
      onError: (error: unknown) => {
        const status = isAxiosError(error) ? error.response?.status : undefined;
        if (status === 429) {
          setServerError("Too many requests. Please wait before requesting another link.");
        } else if (status === 422) {
          setServerError("Please check your email address and try again.");
        } else {
          setServerError("We couldn’t request a reset link. Check your connection and try again later.");
        }
      },
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="text-center sm:text-left">
        <h2 className="mt-8 text-3xl font-bold tracking-tight text-[#202d27]">
          Reset your password
        </h2>
        <p className="mt-2 text-sm text-[#5a685f]">
          Remembered it?{" "}
          <Link
            href="/login"
            className="font-medium text-brand-green hover:underline transition-colors"
          >
            Sign in here
          </Link>
        </p>
      </div>

      <div className="mt-10">
        {acknowledgement ? (
          <div className="space-y-5">
            <div role="status" className="p-4 text-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-800 rounded-lg">
              {acknowledgement}
            </div>
            <p className="text-sm leading-6 text-[#5a685f]">Check your inbox and spam folder. If a link arrives, use it to choose a new password.</p>
            <Link href="/login" className="journey-primary w-full">Return to sign in</Link>
            <button type="button" className="journey-secondary w-full" onClick={() => setAcknowledgement(null)}>Request another link</button>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                disabled={isRequestingReset}
                autoComplete="email"
                {...register("email")}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "email-error" : undefined}
                className={errors.email ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {errors.email && (
                <p id="email-error" role="alert" className="text-xs text-red-700 mt-1">{errors.email.message}</p>
              )}
            </div>

            {serverError && (
              <div role="alert" className="p-3 text-sm bg-red-500/10 border border-red-500/20 text-red-700 rounded-lg">
                {serverError}
              </div>
            )}

            <div>
              <Button type="submit" className="w-full" isLoading={isRequestingReset}>
                Send reset link
              </Button>
            </div>
          </form>
        )}
      </div>
    </motion.div>
  );
}
