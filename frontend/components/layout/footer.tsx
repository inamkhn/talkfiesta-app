import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-gray-50 py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4 lg:grid-cols-5">
          <div className="col-span-2 lg:col-span-2">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <span className="text-2xl">🎉</span>
              <span className="font-serif text-xl font-bold tracking-tight text-brand-green">
                TalkFiesta
              </span>
            </Link>
            <p className="text-sm text-gray-500 max-w-xs">
              Master English in 21 Days with AI-Powered Speaking, Vocabulary & Writing Practice.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Product</h3>
            <ul className="space-y-3 text-sm text-gray-500">
              <li><Link href="#features" className="hover:text-brand-green">Features</Link></li>
              <li><Link href="#pricing" className="hover:text-brand-green">Pricing</Link></li>
              <li><Link href="#how-it-works" className="hover:text-brand-green">How It Works</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Company</h3>
            <ul className="space-y-3 text-sm text-gray-500">
              <li><Link href="#" className="hover:text-brand-green">About</Link></li>
              <li><Link href="#" className="hover:text-brand-green">Blog</Link></li>
              <li><Link href="#" className="hover:text-brand-green">Contact</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Legal</h3>
            <ul className="space-y-3 text-sm text-gray-500">
              <li><Link href="#" className="hover:text-brand-green">Privacy Policy</Link></li>
              <li><Link href="#" className="hover:text-brand-green">Terms of Service</Link></li>
            </ul>
          </div>
        </div>
        <div className="mt-12 border-t border-gray-200 pt-8 text-sm text-gray-400">
          <p>&copy; {new Date().getFullYear()} TalkFiesta. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
