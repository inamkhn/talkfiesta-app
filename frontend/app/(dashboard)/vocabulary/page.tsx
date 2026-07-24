"use client";

import { useState } from "react";
import { useDailyVocabulary, useVocabBank } from "@/hooks/useVocabulary";
import { VocabPracticeWizard } from "@/components/vocabulary/VocabPracticeWizard";
import { useAuthStore } from "@/store/authStore";
import { Loader2, BookOpen, Layers, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export default function VocabularyPage() {
  const { learningProfile } = useAuthStore();
  const currentDay = learningProfile?.current_day || 1;

  const [activeTab, setActiveTab] = useState<"practice" | "bank">("practice");
  const [bankPage, setBankPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");

  const { data: dailyData, isLoading: isLoadingDaily } = useDailyVocabulary(currentDay);
  const { data: bankData, isLoading: isLoadingBank } = useVocabBank(bankPage, 10, searchTerm);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-900 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Vocabulary Track</h1>
          <p className="text-neutral-400 mt-1">Master daily words and expand your vocabulary bank.</p>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center p-1 bg-neutral-950 border border-neutral-800 rounded-xl shrink-0">
          <button
            onClick={() => setActiveTab("practice")}
            className={cn(
              "flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === "practice" ? "bg-neutral-800 text-white shadow" : "text-neutral-400 hover:text-white"
            )}
          >
            <Layers size={16} className="mr-2" /> Daily Practice
          </button>
          <button
            onClick={() => setActiveTab("bank")}
            className={cn(
              "flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === "bank" ? "bg-neutral-800 text-white shadow" : "text-neutral-400 hover:text-white"
            )}
          >
            <BookOpen size={16} className="mr-2" /> Word Bank
          </button>
        </div>
      </div>

      {/* Tab Contents */}
      {activeTab === "practice" ? (
        isLoadingDaily ? (
          <div className="flex h-[50vh] items-center justify-center">
            <Loader2 className="animate-spin text-neutral-500" size={32} />
          </div>
        ) : dailyData ? (
          <VocabPracticeWizard data={dailyData} />
        ) : (
          <div className="text-center py-12 text-rose-400">Failed to load today's vocabulary data.</div>
        )
      ) : (
        <div className="space-y-6">
          {/* Search bar */}
          <div className="relative max-w-md">
            <Search className="absolute left-3.5 top-3.5 text-neutral-500" size={18} />
            <input
              type="text"
              placeholder="Search your word bank..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-neutral-950 border border-neutral-800 rounded-xl text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-neutral-700"
            />
          </div>

          {/* Bank Table / Grid */}
          {isLoadingBank ? (
            <div className="flex h-[40vh] items-center justify-center">
              <Loader2 className="animate-spin text-neutral-500" size={32} />
            </div>
          ) : bankData && bankData.items.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {bankData.items.map((item) => (
                  <div key={item.id} className="p-4 rounded-xl border border-neutral-800 bg-neutral-950 space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-lg font-bold text-white">{item.word}</h4>
                      <span className="text-xs px-2.5 py-0.5 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-400 font-medium">
                        {item.status}
                      </span>
                    </div>
                    <p className="text-sm text-neutral-300">{item.definition}</p>
                    <div className="flex items-center justify-between pt-2 text-xs text-neutral-500 border-t border-neutral-900">
                      <span>Mastery: {item.mastery_level}%</span>
                      {item.part_of_speech && <span className="capitalize">{item.part_of_speech}</span>}
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {bankData.total_pages > 1 && (
                <div className="flex items-center justify-center space-x-2 pt-4">
                  <button
                    disabled={bankPage === 1}
                    onClick={() => setBankPage(p => p - 1)}
                    className="px-3 py-1.5 rounded-lg border border-neutral-800 text-xs font-medium text-neutral-400 hover:text-white disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-neutral-500">Page {bankPage} of {bankData.total_pages}</span>
                  <button
                    disabled={bankPage === bankData.total_pages}
                    onClick={() => setBankPage(p => p + 1)}
                    className="px-3 py-1.5 rounded-lg border border-neutral-800 text-xs font-medium text-neutral-400 hover:text-white disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-neutral-500 border border-neutral-900 rounded-2xl bg-neutral-950">
              No words found in your word bank yet.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
