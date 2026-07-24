import { motion } from "framer-motion";
import { DashboardSummaryResponse } from "@/lib/api/types";
import { Flame, Clock, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

export function ProgressOverview({ summary }: { summary: DashboardSummaryResponse }) {
  const practiceMins = Math.round(summary.today_progress.total_practice_seconds / 60);

  const cards = [
    {
      title: "Today's Practice",
      value: `${practiceMins} min`,
      icon: Clock,
      color: "text-blue-400",
      bg: "bg-blue-400/10",
      border: "border-blue-400/20"
    },
    {
      title: "Current Streak",
      value: `${summary.current_streak} days`,
      icon: Flame,
      color: "text-orange-400",
      bg: "bg-orange-400/10",
      border: "border-orange-400/20"
    },
    {
      title: "Total XP",
      value: summary.total_xp.toLocaleString(),
      icon: Zap,
      color: "text-yellow-400",
      bg: "bg-yellow-400/10",
      border: "border-yellow-400/20"
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <motion.div
            key={c.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={cn(
              "relative p-6 rounded-2xl border bg-neutral-950 overflow-hidden",
              "hover:border-neutral-700 transition-colors",
              c.border
            )}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-400 mb-1">{c.title}</p>
                <h3 className="text-3xl font-bold text-white">{c.value}</h3>
              </div>
              <div className={cn("p-3 rounded-xl", c.bg, c.color)}>
                <Icon size={24} />
              </div>
            </div>
            
            {/* Ambient Background Glow */}
            <div className={cn(
              "absolute -bottom-10 -right-10 w-32 h-32 blur-3xl opacity-20 pointer-events-none",
              c.bg
            )} />
          </motion.div>
        );
      })}
    </div>
  );
}
