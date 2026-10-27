"use client";

import { useState } from "react";
import { WritingSubmissionResponse, FixedIssue } from "@/lib/api/types";
import { useReviseSubmission } from "@/hooks/useWriting";
import {
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  AlignLeft,
  PenTool,
  MessageSquare,
  ChevronRight,
  TrendingUp,
  Award,
  History,
  RefreshCcw,
  Loader2,
  XCircle,
  PlusCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface WritingFeedbackProps {
  submission: WritingSubmissionResponse;
}

// Original essay + up to 3 revisions (mirrors the backend revision cap)
const MAX_VERSIONS = 4;

const getErrorDetail = (err: unknown): string => {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : "Failed to submit revision. Please try again.";
};

export function WritingFeedback({ submission }: WritingFeedbackProps) {
  const versions = submission.versions;
  const latestVersion = versions[versions.length - 1];

  // null = follow the latest version (auto-advances when a revision completes)
  const [selectedVersionNumber, setSelectedVersionNumber] = useState<number | null>(null);
  const viewedVersion =
    (selectedVersionNumber !== null
      ? versions.find((v) => v.version_number === selectedVersionNumber)
      : undefined) || latestVersion;

  // Revision flow — always operates on the LATEST version's text
  const [isRevising, setIsRevising] = useState(false);
  const [reviseContent, setReviseContent] = useState("");
  const reviseMutation = useReviseSubmission(submission.id);
  const revisionsLeft = Math.max(0, MAX_VERSIONS - submission.revision_count);
  const canRevise = submission.status !== "PROCESSING" && revisionsLeft > 0;

  const reviseWordCount = reviseContent.trim()
    ? reviseContent.trim().split(/\s+/).filter(Boolean).length
    : 0;

  const startRevision = () => {
    setReviseContent(latestVersion?.text_content || "");
    reviseMutation.reset();
    setIsRevising(true);
  };

  const submitRevision = () => {
    // On success the submission cache flips to PROCESSING and the parent page
    // swaps to the evaluating panel; polling takes over from there.
    reviseMutation.mutate({
      content: reviseContent,
      word_count: reviseWordCount,
      time_spent_seconds: null,
    });
  };

  const feedback = viewedVersion?.ai_feedback;
  const supervisor = feedback?.supervisor;
  const fixedIssues = viewedVersion?.fixed_issues;

  return (
    <div className="space-y-8 animate-in fade-in duration-700 slide-in-from-bottom-4">
      {/* Version History Selector */}
      {versions.length > 1 && (
        <div className="flex items-center gap-3 flex-wrap bg-neutral-900 border border-neutral-800 rounded-2xl px-5 py-3">
          <div className="flex items-center gap-2 text-neutral-400 text-sm font-medium">
            <History size={16} /> Versions:
          </div>
          {versions.map((v) => (
            <button
              key={v.id}
              onClick={() => setSelectedVersionNumber(v.version_number)}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border",
                v.version_number === viewedVersion?.version_number
                  ? "bg-blue-600/20 border-blue-500/50 text-blue-300"
                  : "bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700"
              )}
            >
              {v.version_number === 1 ? "Original" : `Revision ${v.version_number - 1}`}
              {typeof v.overall_score === "number" && (
                <span className="text-xs bg-neutral-800 px-1.5 py-0.5 rounded font-bold">
                  {v.overall_score}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {!feedback ? (
        <div className="flex flex-col items-center justify-center py-20 text-neutral-400">
          <AlertTriangle size={48} className="mb-4 text-amber-500/50" />
          <h3 className="text-lg font-medium text-white mb-2">No Feedback Available</h3>
          <p>AI feedback hasn&apos;t been generated for this version yet.</p>
        </div>
      ) : (
        <>
          {/* Overview Card */}
          <div className="bg-gradient-to-br from-blue-900/40 to-indigo-900/20 border border-blue-800/50 rounded-2xl p-8 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10">
              <Award size={120} />
            </div>

            <div className="relative z-10 flex flex-col md:flex-row gap-8 items-center md:items-start">
              <div className="shrink-0 flex flex-col items-center justify-center w-32 h-32 bg-neutral-950/50 border-4 border-blue-500 rounded-full shadow-[0_0_30px_rgba(59,130,246,0.3)]">
                <span className="text-4xl font-bold text-white">{viewedVersion.overall_score || supervisor?.overall_score || 0}</span>
                <span className="text-xs text-blue-400 uppercase tracking-widest font-semibold mt-1">Score</span>
              </div>

              <div className="flex-1 text-center md:text-left">
                <h2 className="text-2xl font-bold text-white mb-3">
                  {viewedVersion.version_number > 1
                    ? `Revision ${viewedVersion.version_number - 1} Evaluated`
                    : "Evaluation Complete"}
                </h2>
                <p className="text-blue-100/80 leading-relaxed text-sm md:text-base">
                  {supervisor?.narrative_summary || "Great job completing your writing task! Check the detailed feedback below to see where you excelled and what you can improve."}
                </p>

                <div className="mt-6 flex flex-wrap gap-4 justify-center md:justify-start">
                  <div className="flex items-center gap-2 bg-neutral-950/40 px-4 py-2 rounded-xl border border-white/5">
                    <CheckCircle2 size={16} className="text-emerald-400" />
                    <span className="text-sm text-neutral-300"><strong className="text-white">{submission.word_count}</strong> Words</span>
                  </div>
                  <div className="flex items-center gap-2 bg-neutral-950/40 px-4 py-2 rounded-xl border border-white/5">
                    <TrendingUp size={16} className="text-blue-400" />
                    <span className="text-sm text-neutral-300">Target Reached</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Revision Progress (comparison against the previous version) */}
          {viewedVersion.version_number > 1 && fixedIssues && (
            <div>
              <h3 className="text-white font-semibold flex items-center gap-2 mb-4">
                <RefreshCcw size={18} className="text-blue-400" />
                Revision Progress
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FixedIssueGroup
                  title="Issues Fixed"
                  issues={fixedIssues.fixed_issues}
                  icon={<CheckCircle2 size={16} className="text-emerald-400" />}
                  accent="emerald"
                  emptyText="No previously flagged issues were fixed."
                />
                <FixedIssueGroup
                  title="Still Present"
                  issues={fixedIssues.still_present_issues}
                  icon={<AlertTriangle size={16} className="text-amber-400" />}
                  accent="amber"
                  emptyText="Nothing left over — clean slate!"
                />
                <FixedIssueGroup
                  title="Newly Introduced"
                  issues={fixedIssues.new_issues_introduced}
                  icon={<PlusCircle size={16} className="text-rose-400" />}
                  accent="rose"
                  emptyText="No new issues introduced."
                />
              </div>
            </div>
          )}

          {/* Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Grammar"
              score={feedback.grammar?.score}
              icon={<PenTool className="text-rose-400" />}
              color="rose"
            />
            <MetricCard
              title="Vocabulary"
              score={feedback.vocabulary?.score}
              icon={<BookOpen className="text-amber-400" />}
              color="amber"
            />
            <MetricCard
              title="Structure"
              score={feedback.structure?.score}
              icon={<AlignLeft className="text-emerald-400" />}
              color="emerald"
            />
            <MetricCard
              title="Coherence"
              score={feedback.coherence?.score}
              icon={<MessageSquare className="text-indigo-400" />}
              color="indigo"
            />
          </div>

          {/* Detailed Feedback Sections */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-6">
              <SectionCard title="Grammar & Mechanics" icon={<PenTool size={20} className="text-rose-400" />}>
                {feedback.grammar?.issues && feedback.grammar.issues.length > 0 ? (
                  <div className="space-y-4">
                    {feedback.grammar.issues.map((issue, idx) => (
                      <div key={idx} className="bg-neutral-950 border border-rose-900/30 rounded-xl p-4">
                        <div className="flex items-start gap-3">
                          <div className="mt-1 bg-rose-500/20 p-1 rounded">
                            <AlertTriangle size={14} className="text-rose-400" />
                          </div>
                          <div className="flex-1 space-y-2">
                            <p className="text-sm text-neutral-400 line-through decoration-rose-500/50">{issue.original_text}</p>
                            <p className="text-sm font-medium text-emerald-400">{issue.replacement_text}</p>
                            <p className="text-xs text-neutral-500 mt-2">{issue.explanation}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-400 text-center py-4">No major grammar issues found. Great work!</p>
                )}
              </SectionCard>

              <SectionCard title="Vocabulary Suggestions" icon={<BookOpen size={20} className="text-amber-400" />}>
                {feedback.vocabulary?.suggestions && feedback.vocabulary.suggestions.length > 0 ? (
                  <div className="space-y-4">
                    {feedback.vocabulary.suggestions.map((sug, idx) => (
                      <div key={idx} className="bg-neutral-950 border border-amber-900/30 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-sm font-medium text-neutral-300 bg-neutral-800 px-2 py-1 rounded">{sug.original_word}</span>
                          <ChevronRight size={14} className="text-neutral-600" />
                          <span className="text-sm font-bold text-amber-400 bg-amber-900/20 px-2 py-1 rounded">{sug.suggested_word}</span>
                        </div>
                        <p className="text-xs text-neutral-500">{sug.explanation}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-400 text-center py-4">Your vocabulary usage is excellent.</p>
                )}
              </SectionCard>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              <SectionCard title="Structure & Flow" icon={<AlignLeft size={20} className="text-emerald-400" />}>
                {feedback.structure?.notes && feedback.structure.notes.length > 0 ? (
                  <ul className="space-y-3">
                    {feedback.structure.notes.map((note, idx) => (
                      <li key={idx} className="flex gap-3 text-sm text-neutral-300 bg-neutral-950 p-3 rounded-lg border border-neutral-800/50">
                        <span className="text-emerald-500 mt-0.5">•</span>
                        <span>{note}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-neutral-400 text-center py-4">Structure analysis unavailable.</p>
                )}
              </SectionCard>

              <SectionCard title="Task Response & Coherence" icon={<MessageSquare size={20} className="text-indigo-400" />}>
                {feedback.coherence?.topic_relevance && (
                  <div className="mb-4 bg-indigo-900/20 border border-indigo-900/50 p-4 rounded-xl">
                    <h4 className="text-xs text-indigo-400 uppercase font-bold tracking-wider mb-1">Topic Relevance</h4>
                    <p className="text-sm text-indigo-100/90">{feedback.coherence.topic_relevance}</p>
                  </div>
                )}

                {feedback.coherence?.notes && feedback.coherence.notes.length > 0 && (
                  <ul className="space-y-3">
                    {feedback.coherence.notes.map((note, idx) => (
                      <li key={idx} className="flex gap-3 text-sm text-neutral-300 bg-neutral-950 p-3 rounded-lg border border-neutral-800/50">
                        <span className="text-indigo-500 mt-0.5">•</span>
                        <span>{note}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </SectionCard>

              {supervisor?.actionable_tips && supervisor.actionable_tips.length > 0 && (
                <div className="bg-neutral-800/50 border border-neutral-700 rounded-2xl p-6">
                  <h3 className="text-white font-semibold flex items-center gap-2 mb-4">
                    <TrendingUp size={18} className="text-white" />
                    How to Improve Next Time
                  </h3>
                  <ul className="space-y-3">
                    {supervisor.actionable_tips.map((tip, idx) => (
                      <li key={idx} className="flex gap-3 text-sm text-neutral-300">
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-neutral-700 text-neutral-300 text-xs shrink-0 mt-0.5">{idx + 1}</span>
                        <span>{tip}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Revise Panel */}
      {isRevising ? (
        <div className="bg-neutral-900 border border-blue-900/50 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <RefreshCcw size={18} className="text-blue-400" />
              Revise Your Essay
            </h3>
            <span className="text-sm text-neutral-400">{reviseWordCount} words</span>
          </div>
          <p className="text-sm text-neutral-400">
            Apply the feedback above, then resubmit. The AI will re-evaluate your essay and show which issues you fixed.
          </p>
          <textarea
            className="w-full h-64 bg-neutral-950 border border-neutral-800 rounded-xl p-4 text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 resize-none font-medium leading-relaxed"
            value={reviseContent}
            onChange={(e) => setReviseContent(e.target.value)}
            placeholder="Edit your essay here..."
          />
          {reviseMutation.isError && (
            <div className="flex items-center gap-2 bg-rose-950/30 border border-rose-900/50 rounded-xl px-4 py-3 text-sm text-rose-300">
              <XCircle size={16} className="shrink-0" />
              {getErrorDetail(reviseMutation.error)}
            </div>
          )}
          <div className="flex items-center justify-end gap-3">
            <button
              onClick={() => setIsRevising(false)}
              disabled={reviseMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-neutral-400 hover:text-white transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={submitRevision}
              disabled={reviseMutation.isPending || reviseWordCount === 0}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {reviseMutation.isPending && <Loader2 size={16} className="animate-spin mr-2" />}
              Submit Revision
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
          <div>
            <h3 className="text-white font-semibold mb-1">Want a better score?</h3>
            <p className="text-sm text-neutral-400">
              {canRevise
                ? `Revise your essay using the feedback above — ${revisionsLeft} revision${revisionsLeft === 1 ? "" : "s"} left.`
                : "Revision limit reached for this submission."}
            </p>
          </div>
          {canRevise && (
            <button
              onClick={startRevision}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors flex items-center shrink-0"
            >
              <RefreshCcw size={16} className="mr-2" />
              Revise Essay
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function FixedIssueGroup({
  title,
  issues,
  icon,
  accent,
  emptyText,
}: {
  title: string;
  issues: FixedIssue[];
  icon: React.ReactNode;
  accent: "emerald" | "amber" | "rose";
  emptyText: string;
}) {
  const accentMap = {
    emerald: "border-emerald-900/50 bg-emerald-950/20",
    amber: "border-amber-900/50 bg-amber-950/20",
    rose: "border-rose-900/50 bg-rose-950/20",
  };

  return (
    <div className={cn("rounded-2xl border p-5", accentMap[accent])}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon}
          <h4 className="text-sm font-semibold text-white">{title}</h4>
        </div>
        <span className="text-xs font-bold text-neutral-300 bg-neutral-900/80 px-2 py-0.5 rounded-full">
          {issues.length}
        </span>
      </div>
      {issues.length > 0 ? (
        <ul className="space-y-2">
          {issues.map((issue, idx) => (
            <li key={idx} className="text-xs text-neutral-300 bg-neutral-950/60 rounded-lg p-3 border border-neutral-800/50">
              <p className="font-medium mb-1">{issue.description}</p>
              {issue.original_text && (
                <p className="text-neutral-500 italic">&ldquo;{issue.original_text}&rdquo;</p>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-neutral-500">{emptyText}</p>
      )}
    </div>
  );
}

function MetricCard({ title, score, icon, color }: { title: string, score?: number, icon: React.ReactNode, color: "rose"|"amber"|"emerald"|"indigo" }) {
  const colorMap = {
    rose: "text-rose-400 border-rose-900/50 bg-rose-950/20",
    amber: "text-amber-400 border-amber-900/50 bg-amber-950/20",
    emerald: "text-emerald-400 border-emerald-900/50 bg-emerald-950/20",
    indigo: "text-indigo-400 border-indigo-900/50 bg-indigo-950/20",
  };

  return (
    <div className={cn("rounded-2xl p-5 border flex flex-col justify-between h-32", colorMap[color])}>
      <div className="flex justify-between items-start">
        <span className="text-sm font-medium text-neutral-300">{title}</span>
        {icon}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn("text-3xl font-bold")}>{score || 0}</span>
        <span className="text-xs text-neutral-500">/ 100</span>
      </div>
    </div>
  );
}

function SectionCard({ title, icon, children }: { title: string, icon: React.ReactNode, children: React.ReactNode }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-neutral-800/50">
        <div className="p-2 bg-neutral-950 rounded-lg border border-neutral-800">
          {icon}
        </div>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
      </div>
      {children}
    </div>
  );
}
