"use client";

import { useState, useEffect } from "react";
import { WritingPromptResponse } from "@/lib/api/types";
import { useSaveDraft, useSubmitWriting } from "@/hooks/useWriting";
import { Clock, Info, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface WritingWorkspaceProps {
  prompt: WritingPromptResponse;
  onSubmissionComplete: (submissionId: string) => void;
  initialContent?: string;
}

export function WritingWorkspace({ prompt, onSubmissionComplete, initialContent = "" }: WritingWorkspaceProps) {
  const [content, setContent] = useState(initialContent);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(
    prompt.time_limit_minutes ? prompt.time_limit_minutes * 60 : null
  );
  
  const saveDraftMutation = useSaveDraft();
  const submitMutation = useSubmitWriting();
  
  // Track save status
  const [saveStatus, setSaveStatus] = useState<"IDLE" | "SAVING" | "SAVED">("IDLE");

  // Word count logic
  const wordCount = content.trim() ? content.trim().split(/\s+/).filter(Boolean).length : 0;
  const isTargetMet = wordCount >= prompt.target_word_count;

  // Auto-save logic (debounce)
  useEffect(() => {
    if (!content) return;
    
    const timeout = setTimeout(() => {
      setSaveStatus("SAVING");
      saveDraftMutation.mutate(
        { prompt_id: prompt.id, content },
        {
          onSuccess: () => setSaveStatus("SAVED"),
          onError: () => setSaveStatus("IDLE"),
        }
      );
    }, 3000); // 3 second debounce

    return () => clearTimeout(timeout);
  }, [content, prompt.id, saveDraftMutation]);

  // Timer logic
  useEffect(() => {
    if (timeRemaining === null || timeRemaining <= 0) return;
    
    const interval = setInterval(() => {
      setTimeRemaining((prev) => (prev !== null && prev > 0 ? prev - 1 : 0));
    }, 1000);
    
    return () => clearInterval(interval);
  }, [timeRemaining]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const handleSubmit = () => {
    if (!isTargetMet) {
      if (!confirm(`You haven't reached the target word count (${prompt.target_word_count} words). Are you sure you want to submit?`)) {
        return;
      }
    }
    
    // Calculate time spent if there was a timer
    let time_spent_seconds = null;
    if (prompt.time_limit_minutes && timeRemaining !== null) {
      time_spent_seconds = prompt.time_limit_minutes * 60 - timeRemaining;
    }

    submitMutation.mutate(
      {
        prompt_id: prompt.id,
        content,
        word_count: wordCount,
        time_spent_seconds,
      },
      {
        onSuccess: (data) => {
          onSubmissionComplete(data.id);
        },
      }
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Left Panel: Prompt Details */}
      <div className="lg:col-span-4 space-y-6">
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-blue-500" />
          <h2 className="text-xl font-bold text-white mb-2">{prompt.prompt_title}</h2>
          <div className="flex flex-wrap gap-2 mb-4">
            <span className="px-2 py-1 bg-neutral-800 text-neutral-300 text-xs rounded font-medium">
              Task Type: {prompt.type}
            </span>
            <span className="px-2 py-1 bg-neutral-800 text-neutral-300 text-xs rounded font-medium">
              Target: {prompt.target_word_count} words
            </span>
          </div>

          {Array.isArray(prompt.focus_areas) && prompt.focus_areas.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="text-xs text-neutral-400 font-medium py-1">Focus Areas:</span>
              {prompt.focus_areas.map((area: string, idx: number) => (
                <span key={idx} className="px-2 py-1 bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs rounded font-medium">
                  {area}
                </span>
              ))}
            </div>
          )}

          <p className="text-neutral-300 text-sm leading-relaxed whitespace-pre-wrap bg-neutral-950 p-4 rounded-xl border border-neutral-800">
            {prompt.prompt_text}
          </p>
        </div>

        {prompt.writing_tips && (
          <div className="bg-blue-900/10 border border-blue-900/50 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-3">
              <Info size={18} className="text-blue-400" />
              <h3 className="text-blue-400 font-semibold text-sm">Writing Tips</h3>
            </div>
            <p className="text-neutral-300 text-sm">{prompt.writing_tips}</p>
          </div>
        )}

        {prompt.sample_outline && (
          <div className="bg-emerald-900/10 border border-emerald-900/50 rounded-2xl p-6">
            <h3 className="text-emerald-400 font-semibold text-sm mb-3">Sample Outline</h3>
            <div className="text-neutral-300 text-sm whitespace-pre-wrap">
              {prompt.sample_outline}
            </div>
          </div>
        )}
      </div>

      {/* Right Panel: Editor */}
      <div className="lg:col-span-8 flex flex-col h-[600px]">
        {/* Editor Toolbar */}
        <div className="flex items-center justify-between bg-neutral-900 border border-b-0 border-neutral-800 rounded-t-2xl px-6 py-4">
          <div className="flex items-center gap-4">
            <div className={cn(
              "flex items-center text-sm font-medium transition-colors",
              isTargetMet ? "text-emerald-400" : "text-neutral-400"
            )}>
              {wordCount} / {prompt.target_word_count} words
            </div>
            
            <div className="flex items-center text-xs text-neutral-500">
              {saveStatus === "SAVING" && (
                <span className="flex items-center"><Loader2 size={12} className="animate-spin mr-1" /> Saving...</span>
              )}
              {saveStatus === "SAVED" && (
                <span className="flex items-center text-emerald-500/70"><CheckCircle2 size={12} className="mr-1" /> Draft saved</span>
              )}
            </div>
          </div>

          {timeRemaining !== null && (
            <div className={cn(
              "flex items-center font-mono text-sm px-3 py-1 rounded-lg",
              timeRemaining < 300 ? "bg-red-500/10 text-red-400" : "bg-neutral-800 text-neutral-300"
            )}>
              <Clock size={14} className="mr-2" />
              {formatTime(timeRemaining)}
            </div>
          )}
        </div>

        {/* Textarea */}
        <textarea
          className="flex-1 w-full bg-neutral-950 border border-neutral-800 p-6 text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 resize-none font-medium leading-relaxed"
          placeholder="Start writing your response here..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          spellCheck={false} // Disable to simulate exam environment (often disabled)
        />

        {/* Footer Actions */}
        <div className="flex items-center justify-between bg-neutral-900 border border-t-0 border-neutral-800 rounded-b-2xl px-6 py-4">
          <div className="flex items-center text-sm text-neutral-400">
            {!isTargetMet && wordCount > 0 && (
              <span className="flex items-center text-amber-400/80">
                <AlertCircle size={14} className="mr-1.5" />
                Write {prompt.target_word_count - wordCount} more words
              </span>
            )}
          </div>
          <button
            onClick={handleSubmit}
            disabled={submitMutation.isPending || wordCount === 0}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {submitMutation.isPending && <Loader2 size={16} className="animate-spin mr-2" />}
            Submit for AI Review
          </button>
        </div>
      </div>
    </div>
  );
}
