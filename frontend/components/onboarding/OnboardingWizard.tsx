"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Goal, CEFRLevel, LearningProfileCreate } from "@/lib/api/types";
import { useOnboarding } from "@/hooks/useOnboarding";
import { GoalSelection } from "./GoalSelection";
import { LevelSelection } from "./LevelSelection";
import { Loader2, ArrowRight, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

export function OnboardingWizard() {
  const [step, setStep] = useState(1);
  const [goal, setGoal] = useState<Goal | null>(null);
  const [level, setLevel] = useState<CEFRLevel | null>(null);

  const { configureProfile, completeOnboarding, isConfiguring, isCompleting } =
    useOnboarding();

  const handleNext = () => {
    if (step === 1 && goal) setStep(2);
    else if (step === 2 && level) {
      submitProfile();
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const submitProfile = () => {
    if (!goal || !level) return;

    const payload: LearningProfileCreate = {
      goal,
      target_cefr_level: level,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };

    configureProfile(payload, {
      onSuccess: () => {
        completeOnboarding();
      },
    });
  };

  const isNextDisabled = (step === 1 && !goal) || (step === 2 && !level);
  const isLoading = isConfiguring || isCompleting;

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col items-center justify-center min-h-[70vh] p-6">
      {/* Progress Bar */}
      <div className="w-full max-w-sm mx-auto mb-12">
        <div className="flex justify-between text-xs font-medium text-neutral-500 mb-2 px-1">
          <span
            className={
              step >= 1 ? "text-white transition-colors" : "transition-colors"
            }
          >
            Goal
          </span>
          <span
            className={
              step >= 2 ? "text-white transition-colors" : "transition-colors"
            }
          >
            Level
          </span>
        </div>
        <div className="h-2 w-full bg-neutral-900 rounded-full overflow-hidden flex">
          <motion.div
            className="h-full bg-gradient-to-r from-blue-500 to-indigo-500"
            initial={{ width: "50%" }}
            animate={{ width: step === 1 ? "50%" : "100%" }}
            transition={{ duration: 0.4, ease: "easeInOut" }}
          />
        </div>
      </div>

      <div className="w-full relative min-h-[400px]">
        <AnimatePresence mode="wait" custom={step}>
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0"
            >
              <GoalSelection selectedGoal={goal} onSelect={setGoal} />
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0"
            >
              <LevelSelection selectedLevel={level} onSelect={setLevel} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation Footer */}
      <div className="w-full max-w-2xl mx-auto mt-12 flex items-center justify-between border-t border-neutral-800 pt-6">
        <button
          onClick={handleBack}
          disabled={step === 1 || isLoading}
          className={cn(
            "flex items-center px-6 py-3 rounded-xl font-medium transition-all duration-200",
            step === 1 || isLoading
              ? "opacity-0 pointer-events-none"
              : "text-neutral-400 hover:text-white hover:bg-neutral-900",
          )}
        >
          <ArrowLeft size={18} className="mr-2" /> Back
        </button>

        <button
          onClick={handleNext}
          disabled={isNextDisabled || isLoading}
          className={cn(
            "flex items-center px-8 py-3 rounded-xl font-semibold transition-all duration-200",
            isNextDisabled || isLoading
              ? "bg-neutral-800 text-neutral-500 cursor-not-allowed"
              : "bg-white text-black hover:bg-neutral-200 hover:scale-105 active:scale-95 shadow-lg shadow-white/10",
          )}
        >
          {isLoading ? (
            <Loader2 className="animate-spin" size={20} />
          ) : step === 2 ? (
            <>
              Finish <ArrowRight size={18} className="ml-2" />
            </>
          ) : (
            <>
              Continue <ArrowRight size={18} className="ml-2" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
