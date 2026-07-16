import { Button } from "@/components/ui/button";
import { PlayCircle, Check } from "lucide-react";

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-white pt-24 pb-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <div className="inline-flex items-center rounded-full bg-brand-green/10 px-3 py-1 text-sm font-semibold text-brand-green mb-8">
          ✨ AI-Powered English Learning
        </div>
        
        <h1 className="mx-auto max-w-4xl font-serif text-5xl font-bold tracking-tight text-gray-900 sm:text-7xl mb-8 leading-tight">
          Master English in 21 Days
        </h1>
        
        <p className="mx-auto max-w-2xl text-lg text-gray-600 mb-10">
          Speaking. Vocabulary. Writing. One AI coach, real feedback, real progress — every single day.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
          <Button variant="primary" size="lg" className="w-full sm:w-auto text-lg px-8">
            🚀 Start for Free
          </Button>
          <Button variant="outline" size="lg" className="w-full sm:w-auto text-lg px-8">
            <PlayCircle className="w-5 h-5 mr-2" /> Watch 60-sec Demo
          </Button>
        </div>
        
        <div className="flex items-center justify-center gap-8 text-sm text-gray-500 mb-16">
          <span className="flex items-center gap-1"><Check className="w-4 h-4 text-brand-green" /> No credit card required</span>
          <span className="flex items-center gap-1"><Check className="w-4 h-4 text-brand-green" /> Takes 5 minutes to start</span>
        </div>

        {/* Mockup Placeholder */}
        <div className="mx-auto max-w-5xl rounded-2xl border border-gray-200 bg-gray-50 shadow-2xl aspect-video flex items-center justify-center text-gray-400 relative overflow-hidden">
          <div className="absolute top-4 left-4 right-4 flex items-center gap-2">
             <div className="w-3 h-3 rounded-full bg-red-400" />
             <div className="w-3 h-3 rounded-full bg-yellow-400" />
             <div className="w-3 h-3 rounded-full bg-green-400" />
          </div>
          <div className="text-center">
            <p className="font-semibold text-xl mb-2">Fluency: 82/100</p>
            <p className="text-sm">Product Mockup (Speaking Exercise UI)</p>
          </div>
        </div>
      </div>
    </section>
  );
}
