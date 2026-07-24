import { AchievementResponse } from "@/lib/api/types";
import { motion } from "framer-motion";
import { Trophy, Star } from "lucide-react";

export function RecentAchievements({ achievements }: { achievements: AchievementResponse[] }) {
  if (!achievements || achievements.length === 0) {
    return (
      <div className="p-8 border border-neutral-900 rounded-2xl bg-neutral-950 h-full flex flex-col items-center justify-center text-neutral-500">
        <Trophy className="mx-auto mb-3 opacity-20" size={48} />
        <p>No achievements yet.</p>
        <p className="text-sm mt-1">Keep practicing to unlock badges!</p>
      </div>
    );
  }

  return (
    <div className="p-6 border border-neutral-900 rounded-2xl bg-neutral-950 h-full flex flex-col">
      <h3 className="text-lg font-semibold text-white flex items-center mb-6">
        <Star className="mr-2 text-yellow-500" size={18} />
        Recent Achievements
      </h3>
      <div className="grid grid-cols-1 gap-4 flex-1">
        {achievements.map((ach, i) => (
          <motion.div
            key={ach.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center p-4 rounded-xl border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-900 transition-colors"
          >
            <div className="flex-shrink-0 w-12 h-12 bg-yellow-500/10 border border-yellow-500/20 rounded-full flex items-center justify-center text-yellow-500 mr-4">
              <Trophy size={20} />
            </div>
            <div>
              <h4 className="text-white font-medium">{ach.title}</h4>
              <p className="text-xs text-neutral-400 mt-0.5">{ach.description}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
