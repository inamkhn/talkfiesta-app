import { WritingSubmissionResponse } from "@/lib/api/types";
import { FileText, Loader2, CheckCircle2, AlertCircle, Clock } from "lucide-react";

interface WritingPortfolioProps {
  submissions: WritingSubmissionResponse[];
  onSelectSubmission: (id: string) => void;
  isLoading?: boolean;
}

export function WritingPortfolio({ submissions, onSelectSubmission, isLoading }: WritingPortfolioProps) {
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="animate-spin text-blue-500" size={32} />
      </div>
    );
  }

  if (!submissions || submissions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 bg-neutral-900 border border-neutral-800 rounded-2xl">
        <FileText size={48} className="text-neutral-700 mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">No Submissions Yet</h3>
        <p className="text-neutral-400">Your completed writing tasks will appear here.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-in fade-in duration-500">
      {submissions.map((submission) => (
        <div 
          key={submission.id}
          onClick={() => onSelectSubmission(submission.id)}
          className="bg-neutral-900 hover:bg-neutral-800/80 transition-colors border border-neutral-800 hover:border-neutral-700 rounded-2xl p-6 cursor-pointer group flex flex-col"
        >
          <div className="flex justify-between items-start mb-4">
            <div className="bg-neutral-950 p-3 rounded-xl border border-neutral-800 group-hover:border-blue-500/30 group-hover:text-blue-400 transition-colors">
              <FileText size={20} />
            </div>
            <StatusBadge status={submission.status} />
          </div>

          <div className="mb-4">
            <h3 className="text-white font-medium mb-1">
              {new Date(submission.submitted_at).toLocaleDateString("en-US", { month: 'short', day: 'numeric', year: 'numeric' })}
            </h3>
            <div className="flex items-center text-xs text-neutral-500 gap-3">
              <span className="flex items-center">
                <Clock size={12} className="mr-1" /> 
                {new Date(submission.submitted_at).toLocaleTimeString("en-US", { hour: 'numeric', minute: '2-digit' })}
              </span>
              {submission.word_count && <span>• {submission.word_count} words</span>}
            </div>
          </div>

          <div className="mt-auto pt-4 border-t border-neutral-800 flex justify-between items-center">
            <span className="text-sm text-neutral-400">Score</span>
            {submission.overall_score ? (
              <span className="text-xl font-bold text-white">{submission.overall_score}</span>
            ) : (
              <span className="text-sm text-neutral-500 italic">Pending</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "COMPLETED":
      return (
        <div className="flex items-center px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
          <CheckCircle2 size={12} className="mr-1" /> Completed
        </div>
      );
    case "PROCESSING":
      return (
        <div className="flex items-center px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium">
          <Loader2 size={12} className="mr-1 animate-spin" /> Processing
        </div>
      );
    case "FAILED":
      return (
        <div className="flex items-center px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-medium">
          <AlertCircle size={12} className="mr-1" /> Failed
        </div>
      );
    default:
      return (
        <div className="flex items-center px-2.5 py-1 rounded-full bg-neutral-500/10 border border-neutral-500/20 text-neutral-400 text-xs font-medium">
          <Clock size={12} className="mr-1" /> Pending
        </div>
      );
  }
}
