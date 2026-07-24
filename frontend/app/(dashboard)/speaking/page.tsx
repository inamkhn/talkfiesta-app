"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSpeakingExercise, useSubmitAudio, useSpeakingSubmission, useStartLiveSession, useEndLiveSession, useLiveSession } from "@/hooks/useSpeaking";
import { SpeakingWorkspace } from "@/components/speaking/SpeakingWorkspace";
import { SpeakingFeedback } from "@/components/speaking/SpeakingFeedback";
import { LiveSessionWorkspace } from "@/components/speaking/LiveSessionWorkspace";
import { Loader2, AlertCircle } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function SpeakingPage() {
  const [activeTab, setActiveTab] = useState("practice");
  const { learningProfile: profile } = useAuthStore();
  
  const cycle = profile?.current_cycle || 1;
  const day = profile?.current_day || 1;

  // --- Flow A State ---
  const { data: exercise, isLoading: isLoadingExercise, error: exerciseError } = useSpeakingExercise(cycle, day, "CONVERSATIONAL");
  const submitAudioMutation = useSubmitAudio();
  const [activeSubmissionId, setActiveSubmissionId] = useState<string | null>(null);
  
  const { data: submissionData } = useSpeakingSubmission(activeSubmissionId || "");

  const handleAudioSubmit = async (audioUrl: string) => {
    if (!exercise) return;
    try {
      const res = await submitAudioMutation.mutateAsync({
        exercise_id: exercise.id,
        audio_url: audioUrl,
      });
      setActiveSubmissionId(res.id);
      setActiveTab("feedback");
    } catch (err) {
      console.error("Submission failed", err);
    }
  };

  // --- Flow B State ---
  const startLiveMutation = useStartLiveSession();
  const endLiveMutation = useEndLiveSession(activeSubmissionId || ""); // Wait, we need to track liveSessionId
  const [activeLiveSessionId, setActiveLiveSessionId] = useState<string | null>(null);
  const [liveTokenData, setLiveTokenData] = useState<any>(null);

  const { data: liveSessionData } = useLiveSession(activeLiveSessionId || "");
  const { data: liveLinkedSubmission } = useSpeakingSubmission(liveSessionData?.submission_id || "");

  const handleStartLive = async () => {
    try {
      const res = await startLiveMutation.mutateAsync({
        topic: "Applying for a Software Role",
        persona: "INTERVIEWER",
        target_duration_seconds: 120
      });
      setActiveLiveSessionId(res.session_id);
      setLiveTokenData(res);
    } catch (err) {
      console.error("Failed to start live session", err);
    }
  };

  const handleEndLive = async (duration: number, transcript: any[]) => {
    if (!activeLiveSessionId) return;
    try {
      await endLiveMutation.mutateAsync({
        actual_duration_seconds: duration,
        transcript: transcript
      });
      // After ending, we switch to feedback tab to wait for the linked submission
      setActiveTab("feedback");
    } catch (err) {
      console.error("Failed to end live session", err);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Speaking Studio</h1>
          <p className="text-slate-500 mt-1">Practice your pronunciation and conversational skills.</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3 mb-8">
          <TabsTrigger value="practice">Scripted Practice</TabsTrigger>
          <TabsTrigger value="live">Live Interview</TabsTrigger>
          <TabsTrigger value="feedback">Analysis & Feedback</TabsTrigger>
        </TabsList>

        <div className="min-h-[500px]">
          <TabsContent value="practice" className="mt-0">
            {isLoadingExercise ? (
              <div className="flex justify-center items-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
              </div>
            ) : exerciseError ? (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>Failed to load speaking exercise.</AlertDescription>
              </Alert>
            ) : exercise ? (
              <SpeakingWorkspace 
                exercise={exercise} 
                onSubmit={handleAudioSubmit}
                isSubmitting={submitAudioMutation.isPending}
              />
            ) : null}
          </TabsContent>

          <TabsContent value="live" className="mt-0">
            {!activeLiveSessionId ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <h3 className="text-xl font-semibold mb-2">Live Interview Challenge</h3>
                <p className="text-slate-500 mb-6 max-w-md">
                  Practice thinking on your feet with our AI Interviewer. You'll have a real-time conversation evaluated on fluency and grammar.
                </p>
                <button 
                  onClick={handleStartLive}
                  disabled={startLiveMutation.isPending}
                  className="bg-blue-600 text-white px-6 py-2 rounded-full font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center"
                >
                  {startLiveMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Initialize Interview
                </button>
              </div>
            ) : (
              <LiveSessionWorkspace 
                sessionToken={liveTokenData}
                onEndSession={handleEndLive}
                isEnding={endLiveMutation.isPending}
              />
            )}
          </TabsContent>

          <TabsContent value="feedback" className="mt-0">
            {/* Determine which submission to show: Flow A or Flow B */}
            {(() => {
              // Flow A Submission
              if (activeSubmissionId) {
                if (submissionData?.status === "PENDING" || submissionData?.status === "PROCESSING") {
                  return (
                    <div className="flex flex-col items-center justify-center h-64 space-y-4">
                      <div className="relative">
                        <Loader2 className="w-12 h-12 animate-spin text-blue-500" />
                      </div>
                      <h3 className="text-lg font-medium">AI is analyzing your speech...</h3>
                      <p className="text-slate-500 text-sm">Evaluating fluency, grammar, and vocabulary.</p>
                    </div>
                  );
                }
                if (submissionData?.status === "COMPLETED") {
                  return <SpeakingFeedback submission={submissionData} />;
                }
              }

              // Flow B Submission
              if (activeLiveSessionId) {
                if (!liveSessionData?.submission_id || liveLinkedSubmission?.status === "PROCESSING" || liveLinkedSubmission?.status === "PENDING") {
                  return (
                    <div className="flex flex-col items-center justify-center h-64 space-y-4">
                      <Loader2 className="w-12 h-12 animate-spin text-blue-500" />
                      <h3 className="text-lg font-medium">Analyzing interview transcript...</h3>
                    </div>
                  );
                }
                if (liveLinkedSubmission?.status === "COMPLETED") {
                  return <SpeakingFeedback submission={liveLinkedSubmission} />;
                }
              }

              return (
                <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                  <p>Complete a practice exercise or live interview to see your feedback.</p>
                </div>
              );
            })()}
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
