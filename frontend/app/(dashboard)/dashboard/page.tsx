"use client";

import { useProgress } from "@/hooks/useProgress";
import { ProgressOverview } from "@/components/dashboard/ProgressOverview";
import { ActivityHistory } from "@/components/dashboard/ActivityHistory";
import { RecentAchievements } from "@/components/dashboard/RecentAchievements";
import { useAuthStore } from "@/store/authStore";
import { Loader2 } from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { 
    dashboard, 
    isLoadingDashboard,
    history,
    isLoadingHistory
  } = useProgress();

  if (isLoadingDashboard || isLoadingHistory) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="animate-spin text-neutral-500" size={32} />
      </div>
    );
  }

  if (!dashboard) {
    return <div className="text-red-500">Failed to load dashboard data.</div>;
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">
          Welcome back, {user?.first_name || "there"}!
        </h1>
        <p className="text-neutral-400 mt-1">Here is how you're doing today.</p>
      </header>

      <ProgressOverview summary={dashboard} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="lg:col-span-1 min-h-[300px]">
          <ActivityHistory history={history || []} />
        </div>
        <div className="lg:col-span-1 min-h-[300px]">
          <RecentAchievements achievements={dashboard.recent_achievements} />
        </div>
      </div>
    </div>
  );
}
