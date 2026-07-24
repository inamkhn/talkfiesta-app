import { SpeakingSubmissionResponse } from "@/lib/api/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, MessageSquare, AlertTriangle, Lightbulb } from "lucide-react";
import { Progress } from "@/components/ui/progress";

interface SpeakingFeedbackProps {
  submission: SpeakingSubmissionResponse;
}

export function SpeakingFeedback({ submission }: SpeakingFeedbackProps) {
  if (submission.status !== "COMPLETED" || !submission.ai_feedback) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-500">
        <MessageSquare className="w-12 h-12 mb-4 text-slate-300" />
        <p>Feedback is not available yet.</p>
      </div>
    );
  }

  const { ai_feedback, grammar_corrections, vocabulary_suggestions } = submission;

  const renderScoreCard = (title: string, score: number | null | undefined, color: string) => {
    const s = score ?? 0;
    return (
      <Card className="p-4 flex flex-col justify-between">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className={`text-3xl font-bold ${color}`}>{s}</span>
          <span className="text-sm text-slate-400">/ 100</span>
        </div>
        <Progress value={s} className="h-1 mt-3" />
      </Card>
    );
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      
      {/* Top Scores Overview */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="p-4 flex flex-col justify-between col-span-2 md:col-span-1 bg-blue-50 border-blue-200">
          <span className="text-sm font-medium text-blue-800">Overall Score</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-4xl font-black text-blue-600">{submission.overall_score ?? 0}</span>
            <span className="text-sm text-blue-400">/ 100</span>
          </div>
        </Card>
        {renderScoreCard("Fluency", submission.fluency_score, "text-emerald-500")}
        {renderScoreCard("Pronunciation", submission.pronunciation_score, "text-indigo-500")}
        {renderScoreCard("Grammar", submission.grammar_score, "text-amber-500")}
        {renderScoreCard("Vocabulary", submission.vocabulary_score, "text-purple-500")}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Strengths & Improvements */}
        <Card className="p-6 space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-500" /> Key Strengths
          </h3>
          <p className="text-slate-700 leading-relaxed bg-green-50 p-4 rounded-lg">
            {ai_feedback.overall_strengths}
          </p>
          
          <h3 className="text-lg font-semibold flex items-center gap-2 pt-4">
            <AlertTriangle className="w-5 h-5 text-amber-500" /> Areas for Improvement
          </h3>
          <p className="text-slate-700 leading-relaxed bg-amber-50 p-4 rounded-lg">
            {ai_feedback.areas_for_improvement}
          </p>
        </Card>

        {/* Detailed Feedback Sections */}
        <div className="space-y-6">
          
          <Card className="p-6">
            <h3 className="font-semibold mb-2 text-slate-800">Fluency & Delivery</h3>
            <p className="text-sm text-slate-600 mb-4">{ai_feedback.fluency_feedback}</p>
            <div className="flex gap-4 text-sm bg-slate-50 p-3 rounded-md">
              <div><span className="font-medium">WPM:</span> {submission.words_per_minute?.toFixed(1) ?? "N/A"}</div>
              <div><span className="font-medium">Filler Words:</span> {submission.filler_words_count ?? 0}</div>
              <div><span className="font-medium">Pauses:</span> {submission.pause_count ?? 0}</div>
            </div>
          </Card>

          <Card className="p-6 border-amber-200">
            <h3 className="font-semibold mb-2 text-amber-800 flex items-center gap-2">
              Grammar Feedback
            </h3>
            <p className="text-sm text-slate-600 mb-4">{ai_feedback.grammar_feedback}</p>
            
            {grammar_corrections && grammar_corrections.length > 0 && (
              <div className="space-y-3">
                {grammar_corrections.map((corr, idx) => (
                  <div key={idx} className="text-sm bg-amber-50 p-3 rounded border border-amber-100">
                    <div className="line-through text-slate-500 decoration-red-400">{corr.original}</div>
                    <div className="font-medium text-emerald-600 mt-1">{corr.corrected}</div>
                    <div className="text-xs text-slate-500 mt-2">{corr.explanation}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-6 border-purple-200">
            <h3 className="font-semibold mb-2 text-purple-800 flex items-center gap-2">
              <Lightbulb className="w-4 h-4" /> Vocabulary Suggestions
            </h3>
            <p className="text-sm text-slate-600 mb-4">{ai_feedback.vocabulary_feedback}</p>
            
            {vocabulary_suggestions && vocabulary_suggestions.length > 0 && (
              <div className="space-y-3">
                {vocabulary_suggestions.map((sugg, idx) => (
                  <div key={idx} className="text-sm bg-purple-50 p-3 rounded border border-purple-100">
                    <span className="text-slate-500">Instead of </span>
                    <Badge variant="outline" className="bg-white">{sugg.word_used}</Badge>
                    <span className="text-slate-500 mx-2">try</span>
                    <Badge className="bg-purple-600">{sugg.better_alternative}</Badge>
                    <div className="text-xs text-slate-600 mt-2">{sugg.reason}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

        </div>
      </div>
    </div>
  );
}
