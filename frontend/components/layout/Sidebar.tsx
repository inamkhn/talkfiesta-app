"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { 
  LayoutDashboard, 
  Mic, 
  BookOpen, 
  PenTool, 
  User,
  LogOut
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
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
  const { user, logout } = useAuthStore();

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
        {navItems.map((item) => {
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

      {/* User Section */}
      <div className="p-4 border-t border-neutral-900/50 shrink-0">
        <div className="flex items-center justify-between p-3 rounded-xl bg-neutral-900/50 border border-neutral-800/50">
          <div className="flex flex-col truncate pr-2 overflow-hidden">
            <span className="text-sm font-semibold text-white truncate">
              {user?.first_name || "User"} {user?.last_name || ""}
            </span>
            <span className="text-xs text-neutral-500 truncate">{user?.email}</span>
          </div>
          <button 
            onClick={logout}
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
