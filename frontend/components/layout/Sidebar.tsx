"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { 
  LayoutDashboard, 
  Mic, 
  BookOpen, 
  PenTool, 
  User,
  LogOut,
  ShieldCheck
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const navItems = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Speaking", href: "/speaking", icon: Mic },
  { name: "Vocabulary", href: "/vocabulary", icon: BookOpen },
  { name: "Writing", href: "/writing", icon: PenTool },
  { name: "Profile", href: "/profile", icon: User },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  // useAuth().logout revokes the refresh token server-side and clears the
  // query cache — the raw store logout only wipes local state.
  const { logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError("");
    try { await logout(); }
    catch { setLogoutError("Couldn’t sign out. Check your connection and try again."); }
    finally { setLoggingOut(false); }
  };

  return (
    <aside className="w-64 h-screen bg-neutral-950 border-r border-neutral-900 flex-col hidden md:flex sticky top-0 shrink-0">
      {/* Logo */}
      <div className="h-20 flex items-center px-6 border-b border-neutral-900/50 shrink-0">
        <div className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-400 tracking-tight">
          TalkFiesta
        </div>
      </div>

      {/* Nav Links */}
      <div className="flex-1 overflow-y-auto py-6 px-4 space-y-2">
        {[
          ...navItems,
          ...(user?.role === "ADMIN"
            ? [
                {
                  name: "Admin Content",
                  href: "/admin/content-generation",
                  icon: ShieldCheck,
                },
              ]
            : []),
        ].map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;

          return (
            <Link key={item.name} href={item.href} className="relative block group">
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute inset-0 bg-neutral-900 rounded-xl"
                  initial={false}
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                />
              )}
              <div className={cn(
                "relative flex items-center px-4 py-3 rounded-xl transition-colors z-10",
                isActive 
                  ? "text-white" 
                  : "text-neutral-500 group-hover:text-neutral-300 group-hover:bg-neutral-900/30"
              )}>
                <Icon size={20} className={cn("mr-3", isActive ? "text-emerald-400" : "")} />
                <span className="font-medium text-sm">{item.name}</span>
              </div>
            </Link>
          );
        })}
      </div>

      {logoutError && <p role="alert" className="px-4 py-2 text-sm text-red-300">{logoutError}</p>}
      {/* User Section */}
      <div className="p-4 border-t border-neutral-900/50 shrink-0">
        <div className="flex items-center justify-between p-3 rounded-xl bg-neutral-900/50 border border-neutral-800/50">
          <div className="flex flex-col truncate pr-2 overflow-hidden">
            <span className="text-sm font-semibold text-white truncate">
              {user?.display_name || "User"}
            </span>
            <span className="text-xs text-neutral-500 truncate">{user?.email}</span>
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
  );
}
