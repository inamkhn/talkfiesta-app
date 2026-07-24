"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, Square, Play, RotateCcw, Send, Loader2, StopCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SpeakingExerciseResponse } from "@/lib/api/types";
import { Progress } from "@/components/ui/progress";

interface SpeakingWorkspaceProps {
  exercise: SpeakingExerciseResponse;
  onSubmit: (audioUrl: string) => void;
  isSubmitting?: boolean;
}

export function SpeakingWorkspace({ exercise, onSubmit, isSubmitting = false }: SpeakingWorkspaceProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioBase64, setAudioBase64] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const url = URL.createObjectURL(audioBlob);
        setAudioUrl(url);

        // Convert to base64 for mockup submission
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = () => {
          const base64data = reader.result as string;
          setAudioBase64(base64data);
        };
        
        // Stop all tracks to turn off the microphone indicator in browser
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      setAudioUrl(null);
      setAudioBase64(null);

      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Microphone access is required to use the Speaking feature.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    }
  };

  const resetRecording = () => {
    setAudioUrl(null);
    setAudioBase64(null);
    setRecordingTime(0);
  };

  const handlePlayPause = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
  };

  const handleSubmit = () => {
    if (audioBase64) {
      onSubmit(audioBase64);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const progressPercentage = Math.min((recordingTime / exercise.target_duration_seconds) * 100, 100);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left Column: Prompt */}
        <div className="w-full md:w-2/3 space-y-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{exercise.topic}</h2>
            <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
              <Badge variant="outline">{exercise.difficulty_level}</Badge>
              <span>Target Duration: {formatTime(exercise.target_duration_seconds)}</span>
            </div>
          </div>
          
          <Card className="p-6 bg-blue-50/50 border-blue-100">
            <h3 className="font-semibold text-blue-900 mb-2">Prompt</h3>
            <p className="text-lg text-blue-800 leading-relaxed">
              {exercise.prompt_text}
            </p>
          </Card>

          {exercise.instructions && (
            <Card className="p-4 bg-muted/50">
              <h4 className="font-medium mb-1 text-sm text-muted-foreground">Instructions</h4>
              <p className="text-sm">{exercise.instructions}</p>
            </Card>
          )}
          
          {Object.keys(exercise.goal_tags || {}).length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-sm font-medium text-muted-foreground flex items-center">Goals:</span>
              {Object.keys(exercise.goal_tags).map((tag) => (
                <Badge key={tag} variant="secondary" className="bg-indigo-50 text-indigo-700 hover:bg-indigo-100">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Recorder */}
        <div className="w-full md:w-1/3">
          <Card className="p-6 h-full flex flex-col justify-center items-center text-center space-y-6">
            
            {/* Visualizer / Timer */}
            <div className="relative flex flex-col items-center justify-center w-40 h-40 rounded-full border-4 border-slate-100">
              {isRecording ? (
                <>
                  <div className="absolute inset-0 rounded-full border-4 border-red-500 border-t-transparent animate-spin" />
                  <span className="text-3xl font-bold text-red-500 font-mono tracking-tighter">
                    {formatTime(recordingTime)}
                  </span>
                  <span className="text-xs text-red-400 font-medium mt-1 uppercase tracking-wider animate-pulse">Recording</span>
                </>
              ) : audioUrl ? (
                <>
                  <div className="absolute inset-0 rounded-full border-4 border-green-500" />
                  <span className="text-3xl font-bold text-slate-800 font-mono tracking-tighter">
                    {formatTime(recordingTime)}
                  </span>
                  <span className="text-xs text-green-600 font-medium mt-1 uppercase tracking-wider">Ready</span>
                </>
              ) : (
                <>
                  <Mic className="w-12 h-12 text-slate-300 mb-2" />
                  <span className="text-sm text-slate-400 font-medium">Ready to record</span>
                </>
              )}
            </div>

            {/* Progress bar towards target duration */}
            <div className="w-full max-w-[200px] space-y-1">
              <div className="flex justify-between text-xs text-slate-500">
                <span>0:00</span>
                <span>{formatTime(exercise.target_duration_seconds)}</span>
              </div>
              <Progress value={progressPercentage} className="h-2" />
            </div>

            {/* Controls */}
            <div className="flex flex-col gap-3 w-full max-w-[200px]">
              {!isRecording && !audioUrl && (
                <Button 
                  size="lg" 
                  onClick={startRecording}
                  className="w-full rounded-full bg-red-500 hover:bg-red-600 shadow-md hover:shadow-lg transition-all"
                >
                  <Mic className="w-5 h-5 mr-2" /> Start Recording
                </Button>
              )}

              {isRecording && (
                <Button 
                  size="lg" 
                  variant="outline"
                  onClick={stopRecording}
                  className="w-full rounded-full border-red-200 text-red-500 hover:bg-red-50"
                >
                  <StopCircle className="w-5 h-5 mr-2" /> Stop
                </Button>
              )}

              {audioUrl && (
                <>
                  <audio 
                    ref={audioRef} 
                    src={audioUrl} 
                    onEnded={() => setIsPlaying(false)}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    className="hidden" 
                  />
                  
                  <div className="flex gap-2 w-full">
                    <Button 
                      variant="outline" 
                      onClick={handlePlayPause}
                      className="flex-1 rounded-full border-slate-200"
                    >
                      {isPlaying ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4 ml-1" />}
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={resetRecording}
                      disabled={isSubmitting}
                      className="flex-1 rounded-full border-slate-200 text-slate-600"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                  </div>
                  
                  <Button 
                    size="lg" 
                    onClick={handleSubmit} 
                    disabled={isSubmitting || !audioBase64}
                    className="w-full rounded-full bg-blue-600 hover:bg-blue-700 shadow-md"
                  >
                    {isSubmitting ? (
                      <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Submitting</>
                    ) : (
                      <><Send className="w-4 h-4 mr-2" /> Submit Audio</>
                    )}
                  </Button>
                </>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
