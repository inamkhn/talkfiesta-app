import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export function ProductShowcase() {
  return (
    <section className="py-24 bg-white overflow-hidden">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        
        {/* Speaking Showcase (Left Text, Right Mockup) */}
        <div className="grid lg:grid-cols-2 gap-16 items-center mb-32">
          <div>
            <h3 className="text-3xl font-bold text-gray-900 mb-6 font-serif">
              Speak with confidence, not just correctness
            </h3>
            <p className="text-lg text-gray-600 mb-8 leading-relaxed">
              Get instant feedback on fluency, grammar, and even filler words. Practice public speaking, mock interviews, or just casual conversation — with an AI that actually listens.
            </p>
            <Button variant="outline" className="text-brand-green border-brand-green hover:bg-brand-green hover:text-white">
              Try Speaking Practice <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
          <div className="rounded-2xl overflow-hidden border border-gray-200 shadow-xl">
            <img
              src="/speaking-mockup.png"
              alt="TalkFiesta speaking exercise UI with live microphone and real-time transcript"
              className="w-full object-cover"
            />
          </div>
        </div>

        {/* Vocabulary Showcase (Right Text, Left Mockup) */}
        <div className="grid lg:grid-cols-2 gap-16 items-center mb-32">
          <div className="order-2 lg:order-1 rounded-2xl overflow-hidden border border-gray-200 shadow-xl">
            <img
              src="/vocabulary-mockup.png"
              alt="TalkFiesta vocabulary flashcard with spaced repetition quiz"
              className="w-full object-cover"
            />
          </div>
          <div className="order-1 lg:order-2">
            <h3 className="text-3xl font-bold text-gray-900 mb-6 font-serif">
              Learn words you'll actually use
            </h3>
            <p className="text-lg text-gray-600 mb-8 leading-relaxed">
              Master 210 targeted words per cycle. Our spaced repetition system ensures you review words right before you forget them, locking them into your long-term memory forever.
            </p>
            <Button variant="outline" className="text-brand-green border-brand-green hover:bg-brand-green hover:text-white">
              See Vocabulary List <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>

        {/* Writing Showcase (Left Text, Right Mockup) */}
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <h3 className="text-3xl font-bold text-gray-900 mb-6 font-serif">
              Write emails they'll actually read
            </h3>
            <p className="text-lg text-gray-600 mb-8 leading-relaxed">
              Daily prompts tailored to your level. Submit your writing and get line-by-line feedback grading your structure, grammar, and vocabulary upgrades.
            </p>
            <Button variant="outline" className="text-brand-green border-brand-green hover:bg-brand-green hover:text-white">
              Start Writing Prompt <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
          <div className="rounded-2xl overflow-hidden border border-gray-200 shadow-xl">
            <img
              src="/writing-mockup.png"
              alt="TalkFiesta writing feedback interface with AI grammar and vocabulary annotations"
              className="w-full object-cover"
            />
          </div>
        </div>

      </div>
    </section>
  );
}
