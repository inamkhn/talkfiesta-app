import Link from "next/link";
import { AssessmentPreview } from "@/components/onboarding/AssessmentPreview";
export default function Page() {
  return <div className="journey-theme min-h-screen"><header className="border-b border-[#e0e5db] bg-white px-5 py-5"><div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3"><Link href="/" className="text-xl font-bold text-brand-green">TalkFiesta.</Link><span className="text-sm text-[#5a685f]">Public design preview · Sample content only</span></div></header><AssessmentPreview previewOnly /></div>;
}
