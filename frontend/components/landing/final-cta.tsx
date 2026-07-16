import { Button } from "@/components/ui/button";

export function FinalCTA() {
  return (
    <section className="py-24 bg-brand-green text-center px-4">
      <div className="mx-auto max-w-4xl">
        <h2 className="font-serif text-4xl md:text-5xl font-bold text-white mb-8 leading-tight">
          Your English is about to get a lot better.
        </h2>
        
        <div className="flex flex-col items-center justify-center gap-4">
          <Button variant="primary" size="lg" className="w-full sm:w-auto text-xl px-12 py-6 h-auto">
            🚀 Start Your First Day Free
          </Button>
          <p className="text-emerald-100 text-sm mt-4">
            Join in under 5 minutes. No credit card required.
          </p>
        </div>
      </div>
    </section>
  );
}
