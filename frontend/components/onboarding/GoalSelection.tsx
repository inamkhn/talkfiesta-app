import { Goal } from "@/lib/api/types";
import { motion } from "framer-motion";
import { MessageCircle, Briefcase, GraduationCap, Plane } from "lucide-react";
import { cn } from "@/lib/utils";

interface GoalSelectionProps {
  selectedGoal: Goal | null;
  onSelect: (goal: Goal) => void;
}

const goals = [
  {
    id: Goal.FLUENCY,
    title: "Fluency & Conversation",
    description: "Speak confidently in daily life.",
    icon: MessageCircle,
    color: "text-blue-500",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    activeBorder: "border-blue-500",
  },
  {
    id: Goal.BUSINESS,
    title: "Business & Career",
    description: "Master professional communication.",
    icon: Briefcase,
    color: "text-indigo-500",
    bg: "bg-indigo-500/10",
    border: "border-indigo-500/20",
    activeBorder: "border-indigo-500",
  },
  {
    id: Goal.EXAM,
    title: "Exam Preparation",
    description: "Get ready for IELTS, TOEFL, etc.",
    icon: GraduationCap,
    color: "text-purple-500",
    bg: "bg-purple-500/10",
    border: "border-purple-500/20",
    activeBorder: "border-purple-500",
  },
  {
    id: Goal.TRAVEL,
    title: "Travel & Culture",
    description: "Navigate foreign countries easily.",
    icon: Plane,
    color: "text-teal-500",
    bg: "bg-teal-500/10",
    border: "border-teal-500/20",
    activeBorder: "border-teal-500",
  },
];

export function GoalSelection({ selectedGoal, onSelect }: GoalSelectionProps) {
  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-bold tracking-tight text-white">What is your main goal?</h2>
        <p className="text-neutral-400">Choose the primary reason you are learning.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
        {goals.map((g, i) => {
          const Icon = g.icon;
          const isActive = selectedGoal === g.id;
          
          return (
            <motion.button
              key={g.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              onClick={() => onSelect(g.id)}
              className={cn(
                "group relative flex flex-col items-start p-6 rounded-2xl border-2 text-left transition-all duration-200 overflow-hidden",
                "hover:shadow-lg hover:-translate-y-1",
                isActive ? g.activeBorder + " bg-neutral-900/50" : g.border + " bg-neutral-950/50 hover:bg-neutral-900/50"
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="goal-active-bg"
                  className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none"
                  initial={false}
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                />
              )}
              <div className={cn("p-3 rounded-xl mb-4", g.bg, g.color)}>
                <Icon size={28} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-1">{g.title}</h3>
              <p className="text-sm text-neutral-400">{g.description}</p>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
