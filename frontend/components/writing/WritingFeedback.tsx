import { WritingSubmissionResponse } from "@/lib/api/types";
import { 
  CheckCircle2, 
  AlertTriangle, 
  BookOpen, 
  AlignLeft, 
  PenTool, 
  MessageSquare,
  ChevronRight,
  TrendingUp,
  Award
} from "lucide-react";
import { cn } from "@/lib/utils";

interface WritingFeedbackProps {
  submission: WritingSubmissionResponse;
}

export function WritingFeedback({ submission }: WritingFeedbackProps) {
  const latestVersion = submission.versions[submission.versions.length - 1];
  
  if (!latestVersion?.ai_feedback) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-neutral-400">
        <AlertTriangle size={48} className="mb-4 text-amber-500/50" />
        <h3 className="text-lg font-medium text-white mb-2">No Feedback Available</h3>
        <p>AI feedback hasn&apos;t been generated for this submission yet.</p>
      </div>
    );
  }

  const feedback = latestVersion.ai_feedback;
  const supervisor = feedback.supervisor;

  return (
    <div className="space-y-8 animate-in fade-in duration-700 slide-in-from-bottom-4">
      {/* Overview Card */}
      <div className="bg-gradient-to-br from-blue-900/40 to-indigo-900/20 border border-blue-800/50 rounded-2xl p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-10">
          <Award size={120} />
        </div>
        
        <div className="relative z-10 flex flex-col md:flex-row gap-8 items-center md:items-start">
          <div className="shrink-0 flex flex-col items-center justify-center w-32 h-32 bg-neutral-950/50 border-4 border-blue-500 rounded-full shadow-[0_0_30px_rgba(59,130,246,0.3)]">
            <span className="text-4xl font-bold text-white">{latestVersion.overall_score || supervisor?.overall_score || 0}</span>
            <span className="text-xs text-blue-400 uppercase tracking-widest font-semibold mt-1">Score</span>
          </div>
          
          <div className="flex-1 text-center md:text-left">
            <h2 className="text-2xl font-bold text-white mb-3">Evaluation Complete</h2>
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
