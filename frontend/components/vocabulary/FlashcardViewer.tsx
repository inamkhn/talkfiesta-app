"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { WordWithExerciseResponse } from "@/lib/api/types";
import { Volume2, RotateCw, ArrowRight, ArrowLeft, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface FlashcardViewerProps {
  words: WordWithExerciseResponse[];
  onComplete: () => void;
}

export function FlashcardViewer({ words, onComplete }: FlashcardViewerProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  const currentWord = words[currentIndex];

  const handleNext = () => {
    setIsFlipped(false);
    if (currentIndex < words.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      onComplete();
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setIsFlipped(false);
      setCurrentIndex(currentIndex - 1);
    }
  };

  const playAudio = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (currentWord?.audio_url) {
      const audio = new Audio(currentWord.audio_url);
      audio.play();
    } else {
      const utterance = new SpeechSynthesisUtterance(currentWord?.word || "");
      window.speechSynthesis.speak(utterance);
    }
  };

  if (!currentWord) return null;

  return (
    <div className="w-full max-w-xl mx-auto flex flex-col items-center space-y-6">
      {/* Progress header */}
      <div className="w-full flex items-center justify-between text-xs font-semibold text-neutral-400">
        <span>Word {currentIndex + 1} of {words.length}</span>
        <span>{Math.round(((currentIndex + 1) / words.length) * 100)}%</span>
      </div>

      <div className="w-full h-1.5 bg-neutral-900 rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-emerald-500"
          initial={{ width: 0 }}
          animate={{ width: `${((currentIndex + 1) / words.length) * 100}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>

      {/* 3D Flip Card Container */}
      <div
        onClick={() => setIsFlipped(!isFlipped)}
        className="w-full h-80 cursor-pointer perspective-1000 group"
      >
        <motion.div
          animate={{ rotateY: isFlipped ? 180 : 0 }}
          transition={{ duration: 0.6, ease: "easeInOut" }}
          style={{ transformStyle: "preserve-3d" }}
          className="relative w-full h-full rounded-2xl border border-neutral-800 bg-neutral-950 p-8 shadow-xl flex flex-col items-center justify-center text-center group-hover:border-neutral-700 transition-colors"
        >
          {/* FRONT */}
          <div
            style={{ backfaceVisibility: "hidden" }}
            className="absolute inset-0 p-8 flex flex-col items-center justify-center space-y-4"
          >
            <span className="text-xs uppercase tracking-widest text-emerald-400 font-semibold px-3 py-1 bg-emerald-500/10 rounded-full border border-emerald-500/20">
              {currentWord.part_of_speech || "Vocabulary"}
            </span>

            <h2 className="text-4xl font-extrabold text-white tracking-tight">
              {currentWord.word}
            </h2>

            {currentWord.phonetic && (
              <p className="text-neutral-400 font-mono text-sm">{currentWord.phonetic}</p>
            )}

            <button
              onClick={playAudio}
              className="p-3 bg-neutral-900 hover:bg-neutral-800 text-neutral-300 hover:text-white rounded-full transition-colors mt-2"
              title="Listen to pronunciation"
            >
              <Volume2 size={20} />
            </button>

            <div className="absolute bottom-4 flex items-center text-xs text-neutral-500 space-x-1">
              <RotateCw size={12} />
              <span>Click to reveal definition</span>
            </div>
          </div>

          {/* BACK */}
          <div
            style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
            className="absolute inset-0 p-8 flex flex-col items-center justify-center space-y-4 text-center bg-neutral-900/95 rounded-2xl border border-neutral-800"
          >
            <span className="text-xs uppercase tracking-widest text-neutral-400 font-semibold">
              Definition
            </span>

            <p className="text-lg font-medium text-white leading-relaxed">
              {currentWord.definition}
            </p>

            {currentWord.example_sentence && (
              <div className="mt-4 p-3 bg-neutral-950 rounded-xl border border-neutral-800/60 text-xs text-neutral-300 italic">
                "{currentWord.example_sentence}"
              </div>
            )}

            <div className="absolute bottom-4 flex items-center text-xs text-neutral-500 space-x-1">
              <RotateCw size={12} />
              <span>Click to flip back</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Navigation Controls */}
      <div className="w-full flex items-center justify-between pt-4">
        <button
          onClick={handlePrev}
          disabled={currentIndex === 0}
          className={cn(
            "flex items-center px-4 py-2.5 rounded-xl text-sm font-medium transition-colors",
            currentIndex === 0
              ? "opacity-0 pointer-events-none"
              : "text-neutral-400 hover:text-white hover:bg-neutral-900"
          )}
        >
          <ArrowLeft size={16} className="mr-2" /> Previous
        </button>

        <button
          onClick={handleNext}
          className="flex items-center px-6 py-2.5 rounded-xl text-sm font-semibold bg-white text-black hover:bg-neutral-200 transition-all hover:scale-105 active:scale-95 shadow-lg shadow-white/10"
        >
          {currentIndex === words.length - 1 ? (
            <>Start Exercises <CheckCircle2 size={16} className="ml-2 text-emerald-600" /></>
          ) : (
            <>Next Word <ArrowRight size={16} className="ml-2" /></>
          )}
        </button>
      </div>
    </div>
  );
}
