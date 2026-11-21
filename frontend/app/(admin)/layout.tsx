"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowLeft, FileCheck2, Layers, LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const { logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-black text-neutral-100">
      <aside className="hidden md:flex w-64 h-screen sticky top-0 shrink-0 flex-col bg-neutral-950 border-r border-neutral-900">
        <div className="h-20 flex items-center justify-between px-6 border-b border-neutral-900/60">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            <span className="text-lg font-bold tracking-tight text-white">
              TalkFiesta Admin
            </span>
          </div>
        </div>

        <nav className="flex-1 py-6 px-4 space-y-2">
          <Link
            href="/admin/content-generation"
            className={cn(
              "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors",
              pathname?.startsWith("/admin/content-generation")
                ? "bg-neutral-900 text-white"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40"
            )}
          >
            <Layers className="h-4 w-4 text-emerald-400" />
            Content Batches
          </Link>

          <Link
            href="/admin/content-review"
            className={cn(
              "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors",
              pathname?.startsWith("/admin/content-review")
                ? "bg-neutral-900 text-white"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40"
            )}
          >
            <FileCheck2 className="h-4 w-4 text-cyan-400" />
            Content Review
          </Link>

          <Link
            href="/dashboard"
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Learner App
          </Link>
        </nav>

        <div className="p-4 border-t border-neutral-900/60">
          <div className="flex items-center justify-between p-3 rounded-xl bg-neutral-900/50 border border-neutral-800/50">
            <div className="flex flex-col truncate pr-2">
              <span className="text-sm font-semibold text-white truncate">
                {user?.display_name || "Admin"}
              </span>
              <span className="text-xs text-neutral-500 truncate">
                {user?.email}
              </span>
            </div>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              aria-label={loggingOut ? "Signing out" : "Log out"}
              className="p-2 text-neutral-500 hover:text-red-400 hover:bg-neutral-800 rounded-lg transition-colors shrink-0"
              title="Log out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        <header className="md:hidden h-16 border-b border-neutral-900 flex items-center justify-between px-4 bg-neutral-950 shrink-0">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span className="text-base font-bold text-white">
              TalkFiesta Admin
            </span>
          </div>
          <Link
            href="/dashboard"
            className="text-xs text-neutral-400 hover:text-white"
          >
            Learner App
          </Link>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-8 lg:p-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
