import { ClipboardList, Target, Clock, TrendingUp } from "lucide-react";

export function HowItWorks() {
  return (
    <section className="py-24 bg-gray-50" id="how-it-works">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="font-serif text-3xl font-bold text-gray-900 mb-16">
          How it works
        </h2>
        
        <div className="grid gap-12 md:grid-cols-4 relative">
          {/* Connecting line for desktop */}
          <div className="hidden md:block absolute top-8 left-[12.5%] right-[12.5%] h-0.5 border-t-2 border-dashed border-gray-300 z-0"></div>

          {/* Steps */}
          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-brand-green text-white flex items-center justify-center text-xl font-bold shadow-md mb-6 ring-8 ring-gray-50">
              <ClipboardList className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">1. Level Check</h3>
            <p className="text-sm text-gray-500">Take a 5-minute assessment to find your starting point.</p>
          </div>

          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-brand-green text-white flex items-center justify-center text-xl font-bold shadow-md mb-6 ring-8 ring-gray-50">
              <Target className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">2. Personal Plan</h3>
            <p className="text-sm text-gray-500">Get your customized 21-day learning roadmap.</p>
          </div>

          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-brand-green text-white flex items-center justify-center text-xl font-bold shadow-md mb-6 ring-8 ring-gray-50">
              <Clock className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">3. Practice Daily</h3>
            <p className="text-sm text-gray-500">Spend just 10-15 minutes a day completing specific tasks.</p>
          </div>

          <div className="relative z-10 flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-brand-green text-white flex items-center justify-center text-xl font-bold shadow-md mb-6 ring-8 ring-gray-50">
              <TrendingUp className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">4. Track Progress</h3>
            <p className="text-sm text-gray-500">See your fluency scores rise as you complete each cycle.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
