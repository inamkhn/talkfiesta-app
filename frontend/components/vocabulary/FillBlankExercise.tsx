"use client";

import { useState } from "react";
import { WordWithExerciseResponse, FillBlankSubmission, FillBlankResult } from "@/lib/api/types";
import { CheckCircle2, XCircle, ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface FillBlankExerciseProps {
  words: WordWithExerciseResponse[];
  onSubmit: (submission: FillBlankSubmission) => Promise<FillBlankResult>;
  onComplete: () => void;
}

export function FillBlankExercise({ words, onSubmit, onComplete }: FillBlankExerciseProps) {
  // Filter words that have a fill-blank exercise
  const exerciseWords = words.filter(w => w.exercise?.fill_blank_sentence);
  
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswer, setUserAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<FillBlankResult | null>(null);

  const currentWord = exerciseWords[currentIndex];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userAnswer.trim() || !currentWord) return;

    setIsSubmitting(true);
    try {
      const res = await onSubmit({
        word_id: currentWord.id,
        user_answer: userAnswer.trim(),
      });
      setResult(res);
    } catch (err) {
      console.error("Fill blank error", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNextQuestion = () => {
    setResult(null);
    setUserAnswer("");
    if (currentIndex < exerciseWords.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      onComplete();
    }
  };

  if (!currentWord || exerciseWords.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-neutral-400">No fill-in-the-blank exercises available for today.</p>
        <button
          onClick={onComplete}
          className="mt-4 px-6 py-2.5 bg-white text-black font-semibold rounded-xl"
        >
          Finish Session
        </button>
      </div>
    );
  }

  const sentenceParts = currentWord.exercise!.fill_blank_sentence.split("___");

  return (
    <div className="w-full max-w-xl mx-auto space-y-6">
      <div className="flex items-center justify-between text-xs font-semibold text-neutral-400">
        <span>Fill in the Blank ({currentIndex + 1} / {exerciseWords.length})</span>
        <span>Word: {currentWord.word}</span>
      </div>

      <div className="p-8 border border-neutral-800 bg-neutral-950 rounded-2xl space-y-6">
        <div className="text-lg font-medium text-white leading-relaxed">
          {sentenceParts[0]}
          <span className="inline-block border-b-2 border-emerald-500 px-3 font-semibold text-emerald-400">
            {result ? result.correct_answer : userAnswer || "___"}
          </span>
          {sentenceParts[1]}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <input
            type="text"
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            disabled={!!result || isSubmitting}
            placeholder="Type your answer..."
            className="w-full px-4 py-3 rounded-xl bg-neutral-900 border border-neutral-800 text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500 transition-colors"
          />

          {!result ? (
            <button
              type="submit"
              disabled={!userAnswer.trim() || isSubmitting}
              className={cn(
                "w-full py-3 rounded-xl font-semibold flex items-center justify-center transition-all",
                userAnswer.trim() && !isSubmitting
                  ? "bg-white text-black hover:bg-neutral-200"
                  : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
              )}
            >
              {isSubmitting ? <Loader2 className="animate-spin" size={18} /> : "Check Answer"}
            </button>
          ) : (
            <div className="space-y-4">
              <div className={cn(
                "p-4 rounded-xl flex items-center space-x-3 text-sm font-medium border",
                result.is_correct
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-400"
              )}>
                {result.is_correct ? (
                  <>
                    <CheckCircle2 size={20} />
                    <span>Correct! Great job.</span>
                  </>
                ) : (
                  <>
                    <XCircle size={20} />
                    <span>Correct answer: <strong>{result.correct_answer}</strong></span>
                  </>
                )}
              </div>

              <button
                type="button"
                onClick={handleNextQuestion}
                className="w-full py-3 rounded-xl font-semibold bg-white text-black hover:bg-neutral-200 flex items-center justify-center transition-all"
              >
                {currentIndex === exerciseWords.length - 1 ? "Complete Practice" : "Next Question"}
                <ArrowRight size={18} className="ml-2" />
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
