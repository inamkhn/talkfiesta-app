"use client";

import { useState } from "react";
import { WordWithExerciseResponse, MatchSubmission, MatchResult } from "@/lib/api/types";
import { CheckCircle2, XCircle, ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface MatchExerciseProps {
  words: WordWithExerciseResponse[];
  onSubmit: (submission: MatchSubmission) => Promise<MatchResult>;
  onComplete: () => void;
}

export function MatchExercise({ words, onSubmit, onComplete }: MatchExerciseProps) {
  const activeWords = words.slice(0, 5);
  
  const [selectedWordId, setSelectedWordId] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<MatchResult | null>(null);

  const [definitions] = useState(() => {
    return activeWords
      .map(w => ({ wordId: w.id, definition: w.definition }))
      .sort(() => Math.random() - 0.5);
  });

  const handleSelectWord = (wordId: string) => {
    if (result) return;
    setSelectedWordId(wordId);
  };

  const handleSelectDefinition = (def: string) => {
    if (result || !selectedWordId) return;
    setMatches(prev => ({
      ...prev,
      [selectedWordId]: def
    }));
    setSelectedWordId(null);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const submissionPayload: MatchSubmission = {
        pairs: Object.entries(matches).map(([word_id, selected_definition]) => ({
          word_id,
          selected_definition
        }))
      };
      const res = await onSubmit(submissionPayload);
      setResult(res);
    } catch (err) {
      console.error("Match exercise submission error", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isAllMatched = activeWords.length > 0 && activeWords.every(w => matches[w.id]);

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold text-white">Definition Matching</h2>
        <p className="text-sm text-neutral-400">Select a word on the left, then select its matching definition on the right.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        {/* Words Column */}
        <div className="space-y-3">
          <h3 className="text-xs uppercase tracking-wider font-semibold text-neutral-500 mb-2">Words</h3>
          {activeWords.map((item) => {
            const isSelected = selectedWordId === item.id;
            const matchedDef = matches[item.id];
            const pairResult = result?.pairs.find(p => p.word_id === item.id);

            return (
              <button
                key={item.id}
                onClick={() => handleSelectWord(item.id)}
                disabled={!!result}
                className={cn(
                  "w-full text-left p-4 rounded-xl border transition-all flex items-center justify-between",
                  isSelected
                    ? "border-emerald-500 bg-emerald-500/10 text-white"
                    : matchedDef
                    ? "border-neutral-700 bg-neutral-900 text-neutral-200"
                    : "border-neutral-800 bg-neutral-950 hover:bg-neutral-900 text-white",
                  pairResult && (pairResult.is_correct ? "border-emerald-500/80 bg-emerald-500/10" : "border-rose-500/80 bg-rose-500/10")
                )}
              >
                <span className="font-semibold">{item.word}</span>
                {pairResult ? (
                  pairResult.is_correct ? <CheckCircle2 size={18} className="text-emerald-400" /> : <XCircle size={18} className="text-rose-400" />
                ) : matchedDef ? (
                  <span className="text-xs bg-neutral-800 px-2 py-1 rounded text-neutral-400 truncate max-w-[120px]">
                    {matchedDef}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        {/* Definitions Column */}
        <div className="space-y-3">
          <h3 className="text-xs uppercase tracking-wider font-semibold text-neutral-500 mb-2">Definitions</h3>
          {definitions.map((item, idx) => {
            const isAssigned = Object.values(matches).includes(item.definition);

            return (
              <button
                key={idx}
                onClick={() => handleSelectDefinition(item.definition)}
                disabled={!!result || !selectedWordId}
                className={cn(
                  "w-full text-left p-4 rounded-xl border text-sm transition-all",
                  isAssigned
                    ? "border-neutral-800 bg-neutral-900/60 text-neutral-500"
                    : selectedWordId
                    ? "border-neutral-700 bg-neutral-950 hover:border-emerald-500/50 hover:bg-neutral-900 text-white"
                    : "border-neutral-800 bg-neutral-950 text-neutral-500 cursor-not-allowed"
                )}
              >
                {item.definition}
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer Controls */}
      <div className="flex justify-between items-center pt-6 border-t border-neutral-900">
        {result && (
          <div className="text-sm font-semibold text-emerald-400">
            Score: {result.score} / {activeWords.length}
          </div>
        )}

        <div className="ml-auto">
          {!result ? (
            <button
              onClick={handleSubmit}
              disabled={!isAllMatched || isSubmitting}
              className={cn(
                "flex items-center px-6 py-2.5 rounded-xl text-sm font-semibold transition-all",
                isAllMatched && !isSubmitting
                  ? "bg-white text-black hover:bg-neutral-200 hover:scale-105"
                  : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
              )}
            >
              {isSubmitting ? <Loader2 className="animate-spin" size={18} /> : "Submit Matching"}
            </button>
          ) : (
            <button
              onClick={onComplete}
              className="flex items-center px-6 py-2.5 rounded-xl text-sm font-semibold bg-white text-black hover:bg-neutral-200 transition-all hover:scale-105"
            >
              Next Exercise <ArrowRight size={16} className="ml-2" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
