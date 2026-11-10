"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { isAxiosError } from "axios";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { GoogleSignIn } from "@/components/auth/GoogleSignIn";
import { useAuth } from "@/hooks/useAuth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const registerSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  first_name: z.string().min(2, "First name is required"),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const { register: registerUser, isRegistering, googleLogin, isGoogleLoggingIn } = useAuth();

  const {
    register: formRegister,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = (data: RegisterFormValues) => {
    if (isRegistering || isGoogleLoggingIn) return;
    setServerError(null);
    registerUser(
      {
        email: data.email,
        password: data.password,
        first_name: data.first_name,
      },
      {
        onError: (error: unknown) => {
          const detail = isAxiosError<{ detail?: string | { msg?: string }[] }>(error) ? error.response?.data?.detail : undefined;
          if (Array.isArray(detail)) {
            setServerError(detail[0]?.msg || "Registration failed");
          } else if (typeof detail === "string") {
            setServerError(detail);
          } else {
            setServerError("An unexpected error occurred. Please try again.");
          }
        },
      }
    );
  };

  const onGoogleCredential = (token: string) => {
    setServerError(null);
    googleLogin(token, { onError: (error: unknown) => {
      const response = isAxiosError<{ detail?: string }>(error) ? error.response : undefined;
      setServerError(response?.status === 429 ? "Too many sign-in attempts. Please wait and try again." : (typeof response?.data?.detail === "string" ? response.data.detail : "Google sign-in could not be completed. Please try again or sign in with email."));
    } });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="text-center sm:text-left">
        <h2 className="mt-8 text-3xl font-bold tracking-tight text-[#202d27]">
          Create your account
        </h2>
        <p className="mt-2 text-sm text-[#5a685f]">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-brand-green hover:underline transition-colors"
          >
            Sign in here
          </Link>
        </p>
      </div>

      <div className="mt-10">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="space-y-2 flex-1">
              <Label htmlFor="first_name">First Name</Label>
              <Input
                id="first_name"
                type="text"
                {...formRegister("first_name")}
              aria-invalid={!!errors.first_name}
              aria-describedby={errors.first_name ? "first_name-error" : undefined}
                className={errors.first_name ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {errors.first_name && (
                <p id="first_name-error" role="alert" className="text-xs text-red-700 mt-1">{errors.first_name.message}</p>
              )}
            </div>


          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email address</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              {...formRegister("email")}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "email-error" : undefined}
              className={errors.email ? "border-red-500 focus-visible:ring-red-500" : ""}
            />
            {errors.email && (
              <p id="email-error" role="alert" className="text-xs text-red-700 mt-1">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              {...formRegister("password")}
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? "password-error" : undefined}
              className={errors.password ? "border-red-500 focus-visible:ring-red-500" : ""}
            />
            {errors.password && (
              <p id="password-error" role="alert" className="text-xs text-red-700 mt-1">{errors.password.message}</p>
            )}
          </div>

<label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm"><input type="checkbox" className="!h-4 !w-4 accent-[#1a6b45]" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />Show password</label>
          {serverError && (
            <div role="alert" className="p-3 text-sm bg-red-500/10 border border-red-500/20 text-red-700 rounded-lg">
              {serverError}
            </div>
          )}

          <div>
            <Button
              type="submit"
              className="w-full"
              disabled={isGoogleLoggingIn} isLoading={isRegistering}
            >
              Sign up
            </Button>
          </div>
        </form>

        <div className="mt-8">
          <div className="relative">
            <div className="absolute inset-0 flex items-center" aria-hidden="true">
              <div className="w-full border-t border-[#dce4d7]" />
            </div>
            <div className="relative flex justify-center text-sm font-medium leading-6">
              <span className="bg-white px-6 text-[#5a685f]">
                Or continue with
              </span>
            </div>
          </div>

          <div className="mt-6">
            <GoogleSignIn onCredential={onGoogleCredential} disabled={isRegistering || isGoogleLoggingIn} pending={isGoogleLoggingIn} />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
