"use client";

import { useState } from "react";
import { Plus, Minus } from "lucide-react";

const faqs = [
  {
    question: "Is this better than Duolingo or Babbel?",
    answer: "Unlike traditional apps that focus heavily on multiple-choice games and vocabulary matching, TalkFiesta is designed for actual conversational fluency. We use real-time AI to simulate human conversation, provide targeted feedback on your speech, and grade long-form writing."
  },
  {
    question: "Do I need to already speak some English to start?",
    answer: "Yes, TalkFiesta is best suited for learners who have at least a basic (A2) to intermediate (B1) understanding of English. Our program helps you transition from 'understanding' English to actively 'using' it with confidence."
  },
  {
    question: "How does the AI actually give feedback?",
    answer: "For speaking, our AI transcribes your audio, analyzes grammar, word choice, and filler words, and gives you a fluency score. For writing, it acts like a human tutor, highlighting structural weaknesses and suggesting vocabulary upgrades."
  },
  {
    question: "Is my voice and data private?",
    answer: "Absolutely. We do not use your personal voice data or written essays to train our core AI models, and all interactions are securely encrypted."
  },
  {
    question: "What if I miss a day — do I lose my progress?",
    answer: "No! Life happens. We encourage a 21-day streak, but your progress is always saved. You can pick up right where you left off without being penalized."
  }
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section className="py-24 bg-white" id="faq">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-center font-serif text-4xl font-bold text-gray-900 mb-12">
          Frequently Asked Questions
        </h2>
        
        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <div 
              key={index} 
              className="border border-gray-200 rounded-xl overflow-hidden transition-all duration-200 hover:border-gray-300"
            >
              <button
                className="w-full flex justify-between items-center px-6 py-4 text-left bg-white hover:bg-gray-50 focus:outline-none"
                onClick={() => setOpenIndex(openIndex === index ? null : index)}
              >
                <span className="font-semibold text-gray-900">{faq.question}</span>
                {openIndex === index ? (
                  <Minus className="w-5 h-5 text-gray-500 shrink-0" />
                ) : (
                  <Plus className="w-5 h-5 text-gray-500 shrink-0" />
                )}
              </button>
              
              {openIndex === index && (
                <div className="px-6 pb-5 bg-white text-gray-600 leading-relaxed">
                  {faq.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
