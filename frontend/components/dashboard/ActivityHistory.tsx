import { DailyProgressResponse } from "@/lib/api/types";
import { motion } from "framer-motion";

export function ActivityHistory({ history }: { history: DailyProgressResponse[] }) {
  // Simple 7-day bar chart
  const last7Days = history.slice(-7);
  
  // Find max seconds to normalize height
  const maxSeconds = Math.max(...last7Days.map(d => d.total_practice_seconds), 1);

  if (last7Days.length === 0) {
    return (
      <div className="p-6 border border-neutral-900 rounded-2xl bg-neutral-950 h-full flex flex-col items-center justify-center text-neutral-500">
        <p>No activity yet.</p>
        <p className="text-sm mt-1">Start practicing to see your chart!</p>
      </div>
    );
  }

  return (
    <div className="p-6 border border-neutral-900 rounded-2xl bg-neutral-950 h-full">
      <h3 className="text-lg font-semibold text-white mb-6">Activity History</h3>
      
      <div className="flex items-end justify-between h-48 px-2">
        {last7Days.map((day, i) => {
          const heightPercent = (day.total_practice_seconds / maxSeconds) * 100;
          const mins = Math.round(day.total_practice_seconds / 60);
          const [year, month, dayNum] = day.date.split("-").map(Number);
          const dateObj = new Date(year, month - 1, dayNum);
          const dayName = dateObj.toLocaleDateString("en-US", { weekday: "short" });

          return (
            <div key={day.id} className="flex flex-col items-center group relative w-full px-1">
              {/* Tooltip */}
              <div className="absolute -top-10 opacity-0 group-hover:opacity-100 transition-opacity bg-neutral-800 text-white text-xs py-1 px-2 rounded whitespace-nowrap pointer-events-none z-10">
                {mins} mins
              </div>

              {/* Bar */}
              <div className="w-full max-w-[40px] h-32 flex items-end justify-center rounded-t-sm bg-neutral-900">
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: `${heightPercent}%` }}
                  transition={{ delay: i * 0.1, duration: 0.5, ease: "easeOut" }}
                  className="w-full bg-emerald-500 rounded-t-sm"
                />
              </div>

              {/* Label */}
              <span className="text-xs text-neutral-500 mt-3">{dayName}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
