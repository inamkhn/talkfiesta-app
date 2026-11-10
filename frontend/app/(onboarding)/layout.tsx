import Link from "next/link";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <div className="journey-theme min-h-screen"><header className="border-b border-[#e0e5db] bg-white"><div className="mx-auto flex min-h-20 max-w-5xl items-center justify-between gap-4 px-5"><Link href="/" className="text-xl font-bold text-brand-green">TalkFiesta<span className="text-brand-orange">.</span></Link><span className="text-sm text-[#5a685f]">Your learning setup</span></div></header>{children}</div>;
}
