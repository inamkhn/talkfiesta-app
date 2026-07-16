export function SystemExplainer() {
  return (
    <section className="py-24 bg-brand-green text-white">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="font-serif text-3xl font-bold mb-6">
          This isn't random practice. It's a real program.
        </h2>
        <p className="text-lg text-emerald-100 mb-16 max-w-2xl mx-auto">
          5 cycles. 21 days each. Every cycle gets harder as you do — so you're always being challenged, never bored, never lost.
        </p>

        {/* Visual Path Placeholder */}
        <div className="bg-white/10 rounded-3xl p-8 backdrop-blur-sm border border-white/20 mb-8 overflow-x-auto">
          <div className="flex justify-between items-center min-w-[600px] relative px-4">
            <div className="absolute top-1/2 left-4 right-4 h-1 bg-white/30 -translate-y-1/2 z-0 rounded-full"></div>
            
            {[
              { level: "Foundation", status: "completed" },
              { level: "Intermediate", status: "active" },
              { level: "Advanced", status: "locked" },
              { level: "Expert", status: "locked" },
              { level: "Master", status: "locked" }
            ].map((cycle, i) => (
              <div key={i} className="relative z-10 flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-4 transition-colors ${
                  cycle.status === "completed" ? "bg-white text-brand-green" : 
                  cycle.status === "active" ? "bg-brand-orange text-white ring-4 ring-brand-orange/30" : 
                  "bg-emerald-800 text-emerald-600 border-2 border-emerald-700"
                }`}>
                  {cycle.status === "completed" ? "✓" : i + 1}
                </div>
                <div className={`text-sm font-medium ${
                  cycle.status === "active" ? "text-white" : "text-emerald-200"
                }`}>
                  {cycle.level}
                </div>
                {cycle.status === "active" && (
                  <div className="absolute -top-10 bg-white text-brand-green text-xs font-bold px-3 py-1 rounded-full shadow-lg whitespace-nowrap">
                    You are here
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
