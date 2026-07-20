"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { useLoginApiV1AuthLoginPost } from "@/lib/api/generated/authentication/authentication";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const loginSchema = z.object({
  username: z.string().email("Please enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);

  const { mutate: login, isPending } = useLoginApiV1AuthLoginPost();

  const {
    register: formRegister,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (data: LoginFormValues) => {
    setServerError(null);
    login(
      {
        data: {
          username: data.username,
          password: data.password,
          grant_type: "password",
          scope: "",
          client_id: "",
          client_secret: "",
        },
      },
      {
        onSuccess: (response) => {
          localStorage.setItem("access_token", response.access_token);
          if (response.refresh_token) {
            localStorage.setItem("refresh_token", response.refresh_token);
          }
          router.push("/dashboard");
        },
        onError: (error: any) => {
          const detail = error?.response?.data?.detail;
          if (typeof detail === "string") {
            setServerError(detail);
          } else {
            setServerError("Invalid credentials. Please try again.");
          }
        },
      },
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
          Welcome back
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Don't have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Sign up for free
          </Link>
        </p>
      </div>

      <div className="mt-10">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="username">Email address</Label>
            <Input
              id="username"
              type="email"
              autoComplete="email"
              {...formRegister("username")}
              className={
                errors.username
                  ? "border-red-500 focus-visible:ring-red-500"
                  : ""
              }
            />
            {errors.username && (
              <p className="text-xs text-red-400 mt-1">
                {errors.username.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Password</Label>
              <div className="text-sm">
                <Link
                  href="#"
                  className="font-medium text-indigo-400 hover:text-indigo-300"
                >
                  Forgot password?
                </Link>
              </div>
            </div>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...formRegister("password")}
              className={
                errors.password
                  ? "border-red-500 focus-visible:ring-red-500"
                  : ""
              }
            />
            {errors.password && (
              <p className="text-xs text-red-400 mt-1">
                {errors.password.message}
              </p>
            )}
          </div>

          {serverError && (
            <div className="p-3 text-sm bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg">
              {serverError}
            </div>
          )}

          <div>
            <Button type="submit" className="w-full" isLoading={isPending}>
              Sign in
            </Button>
          </div>
        </form>

        <div className="mt-8">
          <div className="relative">
            <div
              className="absolute inset-0 flex items-center"
              aria-hidden="true"
            >
              <div className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-sm font-medium leading-6">
              <span className="bg-slate-950 px-6 text-slate-400">
                Or continue with
              </span>
            </div>
          </div>

          <div className="mt-6">
            <Button variant="outline" className="w-full" type="button" disabled>
              <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
              Google
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
