"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { useAuth } from "@/hooks/useAuth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const forgotSchema = z.object({
  email: z.string().email("Please enter a valid email"),
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
    setServerError(null);
    requestPasswordReset(data.email, {
      onSuccess: (response) => setAcknowledgement(response.detail),
      onError: (error: any) => {
        const detail = error?.response?.data?.detail;
        if (Array.isArray(detail)) {
          setServerError(detail[0]?.msg || "Request failed");
        } else if (typeof detail === "string") {
          setServerError(detail);
        } else {
          setServerError("An unexpected error occurred. Please try again.");
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
        <h2 className="mt-8 text-3xl font-bold tracking-tight text-white">
          Reset your password
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Remembered it?{" "}
          <Link
            href="/login"
            className="font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Sign in here
          </Link>
        </p>
      </div>

      <div className="mt-10">
        {acknowledgement ? (
          <div className="p-4 text-sm bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded-lg">
            {acknowledgement}
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
                className={errors.email ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {errors.email && (
                <p className="text-xs text-red-400 mt-1">{errors.email.message}</p>
              )}
            </div>

            {serverError && (
              <div className="p-3 text-sm bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg">
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
