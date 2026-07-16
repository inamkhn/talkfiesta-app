import { Award, Briefcase, GraduationCap, Globe2 } from "lucide-react";

export function TrustBar() {
  return (
    <section className="border-y border-gray-100 bg-gray-50 py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <p className="text-center text-sm font-semibold text-gray-500 mb-6 uppercase tracking-wider">
          Trusted by learners preparing for
        </p>
        <div className="flex flex-wrap justify-center gap-8 md:gap-16 opacity-50 grayscale">
          <div className="flex items-center gap-2 font-bold text-lg text-gray-700">
            <GraduationCap className="w-6 h-6" /> IELTS
          </div>
          <div className="flex items-center gap-2 font-bold text-lg text-gray-700">
            <Award className="w-6 h-6" /> TOEFL
          </div>
          <div className="flex items-center gap-2 font-bold text-lg text-gray-700">
            <Briefcase className="w-6 h-6" /> Job Interviews
          </div>
          <div className="flex items-center gap-2 font-bold text-lg text-gray-700">
            <Globe2 className="w-6 h-6" /> Business English
          </div>
        </div>
      </div>
    </section>
  );
}
