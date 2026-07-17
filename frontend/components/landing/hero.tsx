import { Button } from "@/components/ui/button";
import { PlayCircle, Check, Sparkles } from "lucide-react";

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-white pt-24 pb-32">
      {/* Premium Gradient Background Mesh */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[30%] -left-[10%] w-[70%] h-[70%] rounded-full bg-brand-green/5 blur-3xl" />
        <div className="absolute top-[20%] -right-[10%] w-[60%] h-[60%] rounded-full bg-brand-orange/5 blur-3xl" />
        <div className="absolute bottom-0 left-[20%] w-[80%] h-[50%] rounded-full bg-blue-50/50 blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <div className="animate-[fade-in-up_0.8s_ease-out_forwards] opacity-0 inline-flex items-center rounded-full bg-brand-green/10 border border-brand-green/20 px-4 py-1.5 text-sm font-semibold text-brand-green mb-8 shadow-sm">
          <Sparkles className="w-4 h-4 mr-2" /> AI-Powered English Learning
        </div>
        
        <h1 className="animate-[fade-in-up_0.8s_ease-out_0.2s_forwards] opacity-0 mx-auto max-w-4xl font-serif text-5xl font-extrabold tracking-tight text-gray-900 sm:text-7xl mb-8 leading-tight">
          Master English in 21 Days
        </h1>
        
        <p className="animate-[fade-in-up_0.8s_ease-out_0.4s_forwards] opacity-0 mx-auto max-w-2xl text-xl text-gray-600 mb-10 font-medium">
          Speaking. Vocabulary. Writing. One AI coach, real feedback, real progress — every single day.
        </p>
        
        <div className="animate-[fade-in-up_0.8s_ease-out_0.6s_forwards] opacity-0 flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
          <Button variant="primary" size="lg" className="w-full sm:w-auto text-lg px-8 h-14">
            🚀 Start for Free
          </Button>
          <Button variant="secondary" size="lg" className="w-full sm:w-auto text-lg px-8 h-14">
            <PlayCircle className="w-5 h-5 mr-2 text-gray-700" /> Watch 60-sec Demo
          </Button>
        </div>
        
        <div className="animate-[fade-in-up_0.8s_ease-out_0.8s_forwards] opacity-0 flex items-center justify-center gap-8 text-sm font-medium text-gray-500 mb-20">
          <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-brand-green" /> No credit card required</span>
          <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-brand-green" /> Takes 5 minutes to start</span>
        </div>

        {/* Hero App Mockup */}
        <div className="animate-[fade-in-up_1s_ease-out_1s_forwards] opacity-0 relative mx-auto max-w-5xl group">
          {/* Glowing back shadow */}
          <div className="absolute -inset-1 bg-gradient-to-r from-brand-green to-brand-orange rounded-3xl blur-2xl opacity-20 group-hover:opacity-30 transition-opacity duration-700"></div>
          
          <div className="relative rounded-2xl border border-gray-700/50 bg-[#0F1115] shadow-2xl overflow-hidden ring-1 ring-white/10 transform transition-transform duration-700 hover:scale-[1.01]">
            {/* Browser chrome bar */}
            <div className="flex items-center gap-2 px-4 py-3 bg-[#1A1D24] border-b border-gray-800">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E]" />
                <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123]" />
                <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29]" />
              </div>
              <div className="ml-4 flex-1 bg-[#0F1115] border border-gray-800 rounded-md px-3 py-1 text-xs text-gray-500 text-center font-medium max-w-xs mx-auto flex items-center justify-center gap-2 shadow-inner">
                <span className="text-gray-600">🔒</span> app.talkfiesta.com
              </div>
            </div>
            {/* App screenshot */}
            <img
              src="/hero-mockup.png"
              alt="TalkFiesta speaking exercise interface showing real-time AI feedback"
              className="w-full object-cover"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
