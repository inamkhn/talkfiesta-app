import { Bot, Users, BarChart3 } from "lucide-react";

export function AiDifferentiator() {
  return (
    <section className="py-24 bg-gray-900 text-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="font-serif text-4xl font-bold mb-4">
            Not a chatbot. A real AI coach.
          </h2>
          <p className="text-xl text-gray-400">
            Powered by advanced models, customized for language acquisition.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          <div className="bg-gray-800/50 p-8 rounded-2xl border border-gray-700">
            <div className="w-12 h-12 bg-blue-500/20 text-blue-400 rounded-xl flex items-center justify-center mb-6">
              <Bot className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-4">Real-time voice conversations</h3>
            <p className="text-gray-400 leading-relaxed">
              Talk naturally. The AI responds like a real person, not a pre-written script. Interruptions, hesitations, and corrections are handled seamlessly.
            </p>
          </div>

          <div className="bg-gray-800/50 p-8 rounded-2xl border border-gray-700">
            <div className="w-12 h-12 bg-orange-500/20 text-orange-400 rounded-xl flex items-center justify-center mb-6">
              <Users className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-4">Multi-agent mock interviews</h3>
            <p className="text-gray-400 leading-relaxed">
              Practice with an AI HR interviewer, technical interviewer, AND hiring manager. Get comfortable answering tough questions under pressure.
            </p>
          </div>

          <div className="bg-gray-800/50 p-8 rounded-2xl border border-gray-700">
            <div className="w-12 h-12 bg-emerald-500/20 text-emerald-400 rounded-xl flex items-center justify-center mb-6">
              <BarChart3 className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-4">Feedback that's actually specific</h3>
            <p className="text-gray-400 leading-relaxed">
              Not just "good job." You receive exact grammar corrections, word choice upgrades, and a tangible fluency score after every session.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
