"use client";

import { useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { useDailyPrompt, useWritingPortfolio, useSubmission } from "@/hooks/useWriting";
import { WritingWorkspace } from "@/components/writing/WritingWorkspace";
import { WritingPortfolio } from "@/components/writing/WritingPortfolio";
import { WritingFeedback } from "@/components/writing/WritingFeedback";
import { PenTool, Archive, ChevronLeft, Loader2, RefreshCcw } from "lucide-react";
import { cn } from "@/lib/utils";

export default function WritingPage() {
  const { learningProfile } = useAuthStore();
  const currentDay = learningProfile?.current_day || 1;

  const [activeTab, setActiveTab] = useState<"practice" | "portfolio" | "feedback">("practice");
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string | null>(null);

  const { data: dailyPrompt, isLoading: isLoadingPrompt } = useDailyPrompt(currentDay);
  const { data: portfolioData, isLoading: isLoadingPortfolio } = useWritingPortfolio();
  const { data: selectedSubmission, isLoading: isLoadingSubmission } = useSubmission(selectedSubmissionId || "");

  const handleSubmissionComplete = (submissionId: string) => {
    setSelectedSubmissionId(submissionId);
    setActiveTab("feedback");
  };

  const handleSelectSubmission = (id: string) => {
    setSelectedSubmissionId(id);
    setActiveTab("feedback");
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-900 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Writing Track</h1>
          <p className="text-neutral-400 mt-1">Hone your writing skills with daily prompts and AI feedback.</p>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center p-1 bg-neutral-950 border border-neutral-800 rounded-xl shrink-0">
          <button
            onClick={() => {
              setActiveTab("practice");
              setSelectedSubmissionId(null);
            }}
            className={cn(
              "flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === "practice" ? "bg-neutral-800 text-white shadow" : "text-neutral-400 hover:text-white"
            )}
          >
            <PenTool size={16} className="mr-2" /> Daily Practice
          </button>
          <button
            onClick={() => {
              setActiveTab("portfolio");
              setSelectedSubmissionId(null);
            }}
            className={cn(
              "flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === "portfolio" ? "bg-neutral-800 text-white shadow" : "text-neutral-400 hover:text-white"
            )}
          >
            <Archive size={16} className="mr-2" /> Portfolio
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="min-h-[500px]">
        {activeTab === "practice" && (
          <>
            {isLoadingPrompt || isLoadingPortfolio ? (
              <div className="flex justify-center items-center h-64">
                <Loader2 className="animate-spin text-blue-500" size={32} />
              </div>
            ) : dailyPrompt ? (
              <WritingWorkspace 
                key={dailyPrompt.id}
                prompt={dailyPrompt} 
                initialContent={
                  portfolioData?.submissions.find(
                    (s) => s.prompt_id === dailyPrompt.id && s.status === "PENDING"
                  )?.versions[0]?.text_content || ""
                }
                onSubmissionComplete={handleSubmissionComplete}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-64 bg-neutral-900 border border-neutral-800 rounded-2xl">
                <p className="text-neutral-400">No prompt available for today.</p>
              </div>
            )}
          </>
        )}

        {activeTab === "portfolio" && (
          <WritingPortfolio 
            submissions={portfolioData?.submissions || []} 
            onSelectSubmission={handleSelectSubmission}
            isLoading={isLoadingPortfolio}
          />
        )}

        {activeTab === "feedback" && (
          <div className="space-y-6">
            <button 
              onClick={() => setActiveTab("portfolio")}
              className="flex items-center text-sm font-medium text-neutral-400 hover:text-white transition-colors"
            >
              <ChevronLeft size={16} className="mr-1" /> Back to Portfolio
            </button>
            
            {isLoadingSubmission || !selectedSubmission ? (
              <div className="flex flex-col items-center justify-center h-64 space-y-4">
                <Loader2 className="animate-spin text-blue-500" size={40} />
                <p className="text-neutral-400 animate-pulse">Loading submission details...</p>
              </div>
            ) : selectedSubmission.status === "PROCESSING" || selectedSubmission.status === "PENDING" ? (
              <div className="flex flex-col items-center justify-center h-64 bg-neutral-900 border border-neutral-800 rounded-2xl">
                <div className="relative mb-6">
                  <div className="absolute inset-0 bg-blue-500/20 rounded-full blur-xl animate-pulse" />
                  <RefreshCcw size={48} className="text-blue-500 animate-spin relative z-10" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">AI is Evaluating Your Writing</h3>
                <p className="text-neutral-400 max-w-md text-center">
                  Our expert AI panel is analyzing your submission for grammar, vocabulary, structure, and coherence. This usually takes about 10-30 seconds.
                </p>
              </div>
            ) : selectedSubmission.status === "FAILED" ? (
               <div className="flex flex-col items-center justify-center h-64 bg-rose-950/20 border border-rose-900/50 rounded-2xl">
                 <h3 className="text-xl font-bold text-white mb-2">Evaluation Failed</h3>
                 <p className="text-rose-200/70">Something went wrong while evaluating your submission.</p>
               </div>
            ) : (
              <WritingFeedback submission={selectedSubmission} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
