"use client";

import { useState, useEffect, useRef } from "react";
import { Mic, Phone, PhoneOff, User as UserIcon, Bot, Loader2, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { LiveConversationSessionTokenResponse, LiveSessionTranscriptTurn } from "@/lib/api/types";
import { Input } from "@/components/ui/input";

interface LiveSessionWorkspaceProps {
  sessionToken: LiveConversationSessionTokenResponse | null;
  onEndSession: (actualDurationSeconds: number, transcript: LiveSessionTranscriptTurn[]) => void;
  isEnding?: boolean;
}

export function LiveSessionWorkspace({ sessionToken, onEndSession, isEnding = false }: LiveSessionWorkspaceProps) {
  const [isActive, setIsActive] = useState(false);
  const [transcript, setTranscript] = useState<LiveSessionTranscriptTurn[]>([]);
  const [duration, setDuration] = useState(0);
  
  // For mock simulation
  const [mockInput, setMockInput] = useState("");
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (isActive) {
      timerRef.current = setInterval(() => setDuration(prev => prev + 1), 1000);
      
      // Simulate initial bot greeting
      if (transcript.length === 0) {
        setTimeout(() => {
          setTranscript([
            { speaker: "ai", text: "Hello! Thanks for joining. Can you tell me a little bit about yourself?", timestamp_ms: Date.now() }
          ]);
        }, 1000);
      }
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isActive, transcript.length]);

  const handleStart = () => {
    setIsActive(true);
  };

  const handleEnd = () => {
    setIsActive(false);
    onEndSession(duration, transcript);
  };

  // Mock function to simulate speaking instead of real WebSocket audio streaming
  const handleMockSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!mockInput.trim()) return;

    const userText = mockInput.trim();
    setTranscript(prev => [...prev, { speaker: "user", text: userText, timestamp_ms: Date.now() }]);
    setMockInput("");

    // Simulate bot response
    setTimeout(() => {
      const responses = [
        "That's very interesting. Can you elaborate on that?",
        "I see. How did that make you feel?",
        "What was the most challenging part of that experience?",
        "Excellent. Let's move on to the next topic.",
      ];
      const botResponse = responses[Math.floor(Math.random() * responses.length)];
      setTranscript(prev => [...prev, { speaker: "ai", text: botResponse, timestamp_ms: Date.now() }]);
    }, 2000);
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  if (!sessionToken) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
        <p className="text-slate-500">Initializing secure connection...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[600px] border rounded-xl overflow-hidden bg-white shadow-sm">
      {/* Header */}
      <div className="h-16 border-b flex items-center justify-between px-6 bg-slate-50">
        <div className="flex items-center gap-3">
          <Badge variant={isActive ? "default" : "secondary"} className={isActive ? "bg-red-500 animate-pulse" : ""}>
            {isActive ? "LIVE" : "READY"}
          </Badge>
          <span className="font-medium text-slate-700">Interview Session</span>
        </div>
        <div className="font-mono text-xl font-bold text-slate-800">
          {formatTime(duration)}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
        {!isActive && transcript.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
            <div className="w-24 h-24 rounded-full bg-blue-100 flex items-center justify-center">
              <Phone className="w-10 h-10 text-blue-600" />
            </div>
            <div>
              <h3 className="text-xl font-semibold mb-2">Ready to Start?</h3>
              <p className="text-slate-500 max-w-sm">
                Ensure your microphone is connected and you are in a quiet environment.
              </p>
            </div>
            <Button size="lg" onClick={handleStart} className="rounded-full px-8 bg-blue-600 hover:bg-blue-700">
              Start Conversation
            </Button>
          </div>
        ) : (
          transcript.map((turn, idx) => (
            <div key={idx} className={`flex gap-4 ${turn.speaker === "user" ? "flex-row-reverse" : ""}`}>
              <Avatar className={`w-10 h-10 border-2 ${turn.speaker === "user" ? "border-blue-200" : "border-emerald-200"}`}>
                <AvatarFallback className={turn.speaker === "user" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700"}>
                  {turn.speaker === "user" ? <UserIcon className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                </AvatarFallback>
              </Avatar>
              
              <div className={`max-w-[70%] rounded-2xl p-4 ${
                turn.speaker === "user" 
                  ? "bg-blue-600 text-white rounded-tr-sm" 
                  : "bg-white border shadow-sm rounded-tl-sm text-slate-800"
              }`}>
                {turn.text}
              </div>
            </div>
          ))
        )}
        {isActive && transcript.length > 0 && transcript[transcript.length - 1].speaker === "user" && (
          <div className="flex gap-4">
            <Avatar className="w-10 h-10 border-2 border-emerald-200">
              <AvatarFallback className="bg-emerald-100 text-emerald-700">
                <Loader2 className="w-5 h-5 animate-spin" />
              </AvatarFallback>
            </Avatar>
            <div className="bg-white border shadow-sm rounded-2xl p-4 rounded-tl-sm text-slate-400 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" />
              <span className="w-2 h-2 rounded-full bg-slate-300 animate-bounce delay-75" />
              <span className="w-2 h-2 rounded-full bg-slate-300 animate-bounce delay-150" />
            </div>
          </div>
        )}
      </div>

      {/* Footer / Controls */}
      {isActive && (
        <div className="p-4 border-t bg-white">
          <form onSubmit={handleMockSend} className="flex gap-4 items-center">
            <div className="relative flex-1">
              <Mic className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-red-500 animate-pulse" />
              <Input 
                value={mockInput}
                onChange={(e) => setMockInput(e.target.value)}
                placeholder="Type your response to simulate speaking..." 
                className="pl-10"
              />
            </div>
            <Button type="submit" size="icon" variant="secondary">
              <Send className="w-4 h-4" />
            </Button>
            <div className="w-px h-8 bg-slate-200 mx-2" />
            <Button 
              type="button"
              variant="destructive" 
              onClick={handleEnd}
              disabled={isEnding}
              className="gap-2"
            >
              {isEnding ? <Loader2 className="w-4 h-4 animate-spin" /> : <PhoneOff className="w-4 h-4" />}
              End Call
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}
