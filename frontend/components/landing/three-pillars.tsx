import { Mic, BookOpen, PenTool } from "lucide-react";

export function ThreePillars() {
  return (
    <section className="py-24 bg-gray-50 border-t border-gray-100" id="features">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-3">
          {/* Speaking */}
          <div className="rounded-2xl bg-white p-8 shadow-sm border border-gray-100 border-t-4 border-t-blue-500">
            <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
              <Mic className="h-6 w-6" />
            </div>
            <h3 className="mb-4 text-xl font-bold text-gray-900">Speaking</h3>
            <p className="text-gray-600 leading-relaxed">
              Real conversations with AI, public speaking practice, and even mock interviews to build fluency.
            </p>
          </div>

          {/* Vocabulary */}
          <div className="rounded-2xl bg-white p-8 shadow-sm border border-gray-100 border-t-4 border-t-emerald-500">
            <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <BookOpen className="h-6 w-6" />
            </div>
            <h3 className="mb-4 text-xl font-bold text-gray-900">Vocabulary</h3>
            <p className="text-gray-600 leading-relaxed">
              210 words per cycle, retained forever through our smart spaced repetition algorithm.
            </p>
          </div>

          {/* Writing */}
          <div className="rounded-2xl bg-white p-8 shadow-sm border border-gray-100 border-t-4 border-t-purple-500">
            <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
              <PenTool className="h-6 w-6" />
            </div>
            <h3 className="mb-4 text-xl font-bold text-gray-900">Writing</h3>
            <p className="text-gray-600 leading-relaxed">
              Daily prompts graded on grammar, structure & vocabulary — with real, actionable feedback.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
