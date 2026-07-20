export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-slate-950">
      {/* Left side: Branding & Visuals */}
      <div className="relative hidden w-0 flex-1 lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-900 via-slate-900 to-black z-0" />
        
        {/* Decorative blobs */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-blue-600/20 blur-[120px] mix-blend-screen" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-600/20 blur-[120px] mix-blend-screen" />

        <div className="absolute inset-0 flex flex-col justify-center px-12 z-10 text-white">
          <div className="mb-10">
            <h1 className="text-5xl font-bold font-serif mb-4">TalkFiesta</h1>
            <p className="text-xl text-indigo-200/80 max-w-md leading-relaxed">
              Master spoken English with real-time AI interviews, dynamic vocabulary, and personalized feedback.
            </p>
          </div>
          
          <div className="space-y-6">
            <div className="flex items-center space-x-4 bg-white/5 backdrop-blur-md p-4 rounded-2xl border border-white/10 w-fit">
              <div className="flex-shrink-0 w-12 h-12 bg-blue-500/20 rounded-full flex items-center justify-center">
                <span className="text-2xl">🎙️</span>
              </div>
              <div>
                <h3 className="font-semibold">Live AI Interviews</h3>
                <p className="text-sm text-indigo-200/60">Practice speaking under pressure.</p>
              </div>
            </div>

            <div className="flex items-center space-x-4 bg-white/5 backdrop-blur-md p-4 rounded-2xl border border-white/10 w-fit ml-8">
              <div className="flex-shrink-0 w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center">
                <span className="text-2xl">📝</span>
              </div>
              <div>
                <h3 className="font-semibold">Smart Vocabulary</h3>
                <p className="text-sm text-indigo-200/60">Spaced repetition built-in.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right side: Form Content */}
      <div className="flex flex-1 flex-col justify-center px-4 py-12 sm:px-6 lg:flex-none lg:px-20 xl:px-24 relative z-10">
        {/* Mobile background blob */}
        <div className="absolute inset-0 bg-slate-950 z-[-1] lg:hidden" />
        <div className="absolute top-0 right-0 w-full h-full bg-gradient-to-br from-indigo-900/20 to-transparent blur-[100px] z-[-1] lg:hidden" />

        <div className="mx-auto w-full max-w-sm lg:w-96">
          {children}
        </div>
      </div>
    </div>
  );
}
