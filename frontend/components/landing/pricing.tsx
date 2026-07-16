import { Button } from "@/components/ui/button";
import { Check, X } from "lucide-react";

export function Pricing() {
  return (
    <section className="py-24 bg-gray-50" id="pricing">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="font-serif text-4xl font-bold text-gray-900 mb-4">
            Simple, honest pricing
          </h2>
          <p className="text-xl text-gray-600 mb-8">
            Start free. Upgrade when you're ready.
          </p>

          <div className="mx-auto max-w-md bg-orange-50 border border-brand-orange text-orange-900 px-6 py-4 rounded-xl shadow-sm mb-12">
            <p className="font-bold mb-1">🎉 Founding Member Offer</p>
            <p className="text-sm">First 500 users lock in Pro for $15/mo for life (regular $29). <br className="hidden sm:block"/> <span className="font-medium">342 / 500 spots claimed</span></p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto items-start">
          
          {/* Free Tier */}
          <div className="bg-white rounded-3xl p-8 border border-gray-200 shadow-sm">
            <h3 className="text-2xl font-bold text-gray-900 mb-2">FREE</h3>
            <div className="flex items-baseline gap-1 mb-6">
              <span className="text-4xl font-extrabold text-gray-900">$0</span>
              <span className="text-gray-500">/ forever</span>
            </div>
            
            <ul className="space-y-4 mb-8">
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> 1 full cycle (21 days)
              </li>
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Daily vocabulary
              </li>
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Daily writing prompts
              </li>
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Basic speaking exercises
              </li>
              <li className="flex items-start gap-3 text-gray-400">
                <X className="w-5 h-5 shrink-0 mt-0.5" /> Real-time AI conversation
              </li>
              <li className="flex items-start gap-3 text-gray-400">
                <X className="w-5 h-5 shrink-0 mt-0.5" /> Mock interview panel
              </li>
            </ul>
            
            <Button variant="outline" className="w-full text-brand-green border-brand-green hover:bg-brand-green hover:text-white" size="lg">
              Start Free &rarr;
            </Button>
          </div>

          {/* Pro Tier */}
          <div className="bg-white rounded-3xl p-8 border-2 border-brand-green shadow-xl relative">
            <div className="absolute top-0 right-8 -translate-y-1/2 bg-brand-green text-white px-3 py-1 rounded-full text-sm font-bold shadow-sm">
              ⭐ Popular
            </div>
            
            <h3 className="text-2xl font-bold text-gray-900 mb-2">PRO</h3>
            <div className="flex items-baseline gap-1 mb-6">
              <span className="text-4xl font-extrabold text-gray-900">$15</span>
              <span className="text-gray-500">/ month</span>
            </div>
            
            <ul className="space-y-4 mb-8">
              <li className="flex items-start gap-3 text-gray-900 font-medium">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> All 5 cycles unlocked
              </li>
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Everything in Free
              </li>
              <li className="flex items-start gap-3 text-gray-900 font-medium">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Real-time AI conversation
              </li>
              <li className="flex items-start gap-3 text-gray-900 font-medium">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Multi-agent mock interviews
              </li>
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Priority AI feedback (faster)
              </li>
              <li className="flex items-start gap-3 text-gray-700">
                <Check className="w-5 h-5 text-brand-green shrink-0 mt-0.5" /> Downloadable progress reports
              </li>
            </ul>
            
            <Button variant="primary" className="w-full" size="lg">
              Start Pro Trial &rarr;
            </Button>
          </div>

        </div>
        
        <p className="text-center text-sm text-gray-500 mt-8">
          All plans include a 7-day money-back guarantee. Cancel anytime.
        </p>
      </div>
    </section>
  );
}
