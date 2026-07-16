import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Hero } from "@/components/landing/hero";
import { TrustBar } from "@/components/landing/trust-bar";
import { ProblemAgitation } from "@/components/landing/problem-agitation";
import { ThreePillars } from "@/components/landing/three-pillars";
import { ProductShowcase } from "@/components/landing/product-showcase";
import { HowItWorks } from "@/components/landing/how-it-works";
import { SystemExplainer } from "@/components/landing/system-explainer";
import { AiDifferentiator } from "@/components/landing/ai-differentiator";
import { Pricing } from "@/components/landing/pricing";
import { FAQ } from "@/components/landing/faq";
import { FinalCTA } from "@/components/landing/final-cta";

export default function Home() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <Hero />
        <TrustBar />
        <ProblemAgitation />
        <ThreePillars />
        <ProductShowcase />
        <HowItWorks />
        <SystemExplainer />
        <AiDifferentiator />
        <Pricing />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
