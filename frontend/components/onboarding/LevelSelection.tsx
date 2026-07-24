import { CEFRLevel } from "@/lib/api/types";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface LevelSelectionProps {
  selectedLevel: CEFRLevel | null;
  onSelect: (level: CEFRLevel) => void;
}

const levels: { id: CEFRLevel; title: string; description: string }[] = [
  { id: "A1", title: "Beginner", description: "Can understand and use familiar everyday expressions." },
  { id: "A2", title: "Elementary", description: "Can communicate in simple and routine tasks." },
  { id: "B1", title: "Intermediate", description: "Can deal with most situations likely to arise while travelling." },
  { id: "B2", title: "Upper Intermediate", description: "Can interact with a degree of fluency and spontaneity." },
  { id: "C1", title: "Advanced", description: "Can express ideas fluently and spontaneously without much obvious searching." },
  { id: "C2", title: "Mastery", description: "Can understand with ease virtually everything heard or read." },
];

export function LevelSelection({ selectedLevel, onSelect }: LevelSelectionProps) {
  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-bold tracking-tight text-white">Select your target level</h2>
        <p className="text-neutral-400">What level do you want to achieve?</p>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8">
        {levels.map((lvl, i) => {
          const isActive = selectedLevel === lvl.id;
          
          return (
            <motion.button
              key={lvl.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => onSelect(lvl.id)}
              className={cn(
                "relative flex items-center p-4 rounded-xl border transition-all duration-200 overflow-hidden text-left",
                "hover:bg-neutral-900 hover:-translate-y-0.5",
                isActive 
                  ? "border-emerald-500/50 bg-emerald-500/10 shadow-[0_0_15px_rgba(16,185,129,0.1)]" 
                  : "border-neutral-800 bg-neutral-950/50"
              )}
            >
              <div className={cn(
                "flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-lg mr-4 font-bold text-lg border",
                isActive ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-400" : "bg-neutral-900 border-neutral-800 text-neutral-500"
              )}>
                {lvl.id}
              </div>
              <div className="flex-1 pr-8">
                <h3 className={cn("font-semibold", isActive ? "text-emerald-400" : "text-white")}>{lvl.title}</h3>
                <p className="text-xs text-neutral-400 leading-tight mt-1">{lvl.description}</p>
              </div>
              
              {isActive && (
                <motion.div 
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute right-4 text-emerald-500"
                >
                  <Check size={20} />
                </motion.div>
              )}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
