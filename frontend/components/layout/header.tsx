import Link from "next/link";
import { Button } from "@/components/ui/button";

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl">🎉</span>
            <span className="font-serif text-xl font-bold tracking-tight text-brand-green">
              TalkFiesta
            </span>
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-600">
            <Link href="#features" className="hover:text-brand-green transition-colors">Features</Link>
            <Link href="#how-it-works" className="hover:text-brand-green transition-colors">How It Works</Link>
            <Link href="#pricing" className="hover:text-brand-green transition-colors">Pricing</Link>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/login" className="hidden text-sm font-medium text-gray-600 hover:text-brand-green md:block transition-colors">
            Log In
          </Link>
          <Button variant="primary" asChild>
            <Link href="/signup">Get Started &rarr;</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
