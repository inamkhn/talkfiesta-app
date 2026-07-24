"use client";

import { useState } from "react";
import { DayWordsResponse, SessionCompleteResponse } from "@/lib/api/types";
import { useVocabularyMutations } from "@/hooks/useVocabulary";
import { FlashcardViewer } from "./FlashcardViewer";
import { MatchExercise } from "./MatchExercise";
import { FillBlankExercise } from "./FillBlankExercise";
import { motion, AnimatePresence } from "framer-motion";
import { Trophy, Zap, CheckCircle2, ArrowRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

type WizardStage = "flashcards" | "match" | "fill_blank" | "summary";

interface VocabPracticeWizardProps {
  data: DayWordsResponse;
}

export function VocabPracticeWizard({ data }: VocabPracticeWizardProps) {
  const router = useRouter();
  const [stage, setStage] = useState<WizardStage>("flashcards");
  const [startTime] = useState(() => Date.now());
  const [summaryResult, setSummaryResult] = useState<SessionCompleteResponse | null>(null);

  const { submitMatch, submitFillBlank, completeSession, isCompletingSession } = useVocabularyMutations();

  const handleFinishExercises = async () => {
    const practiceSeconds = Math.max(10, Math.round((Date.now() - startTime) / 1000));
    try {
      const res = await completeSession({
        cycle: data.cycle,
        day: data.day,
        words_learned: data.words.length,
        practice_seconds: practiceSeconds,
      });
      setSummaryResult(res);
      setStage("summary");
    } catch (err) {
      console.error("Failed to complete session", err);
      // Fallback transition
      setStage("summary");
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto py-6">
      {/* Wizard Progress Tabs */}
      {stage !== "summary" && (
        <div className="flex items-center justify-center space-x-2 mb-10 text-xs font-semibold">
          <div className={`px-4 py-2 rounded-full border transition-all ${stage === "flashcards" ? "bg-white text-black border-white" : "border-neutral-800 text-neutral-500"}`}>
            1. Learn Words
          </div>
          <div className="w-4 h-[1px] bg-neutral-800" />
          <div className={`px-4 py-2 rounded-full border transition-all ${stage === "match" ? "bg-white text-black border-white" : "border-neutral-800 text-neutral-500"}`}>
            2. Match
          </div>
          <div className="w-4 h-[1px] bg-neutral-800" />
          <div className={`px-4 py-2 rounded-full border transition-all ${stage === "fill_blank" ? "bg-white text-black border-white" : "border-neutral-800 text-neutral-500"}`}>
            3. Fill in Blank
          </div>
        </div>
      )}

      {/* Stage Components */}
      <AnimatePresence mode="wait">
        {stage === "flashcards" && (
          <motion.div key="flashcards" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <FlashcardViewer words={data.words} onComplete={() => setStage("match")} />
          </motion.div>
        )}

        {stage === "match" && (
          <motion.div key="match" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <MatchExercise words={data.words} onSubmit={submitMatch} onComplete={() => setStage("fill_blank")} />
          </motion.div>
        )}

        {stage === "fill_blank" && (
          <motion.div key="fill_blank" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <FillBlankExercise words={data.words} onSubmit={submitFillBlank} onComplete={handleFinishExercises} />
          </motion.div>
        )}

        {stage === "summary" && (
          <motion.div key="summary" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center max-w-md mx-auto space-y-6 py-12">
            <div className="w-20 h-20 bg-emerald-500/10 border border-emerald-500/30 rounded-full flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 size={40} />
            </div>

            <div className="space-y-2">
              <h2 className="text-3xl font-extrabold text-white">Daily Session Completed!</h2>
              <p className="text-sm text-neutral-400">You studied {data.words.length} vocabulary words today.</p>
            </div>

            {summaryResult && (
              <div className="grid grid-cols-2 gap-4 my-6">
                <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-950">
                  <div className="flex items-center justify-center text-yellow-400 mb-1">
                    <Zap size={20} className="mr-1" />
                    <span className="text-2xl font-bold">+{summaryResult.xp_gained}</span>
                  </div>
                  <span className="text-xs text-neutral-500 font-medium">XP Earned</span>
                </div>

                <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-950">
                  <div className="flex items-center justify-center text-orange-400 mb-1">
                    <Trophy size={20} className="mr-1" />
                    <span className="text-2xl font-bold">{summaryResult.new_streak}</span>
                  </div>
                  <span className="text-xs text-neutral-500 font-medium">Day Streak</span>
                </div>
              </div>
            )}

            <button
              onClick={() => router.push("/dashboard")}
              className="w-full py-3 bg-white text-black font-semibold rounded-xl hover:bg-neutral-200 transition-all hover:scale-105 flex items-center justify-center"
            >
              Return to Dashboard <ArrowRight size={18} className="ml-2" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {isCompletingSession && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="text-center space-y-3">
            <Loader2 className="animate-spin text-white mx-auto" size={32} />
            <p className="text-sm text-neutral-400">Finalizing your score...</p>
          </div>
        </div>
      )}
    </div>
  );
}
