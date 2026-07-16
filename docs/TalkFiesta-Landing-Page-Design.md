# 🎉 TalkFiesta — Landing Page Design

**Companion document to `TalkFiesta.md`**

> A full section-by-section design spec for the public landing page — layout, copy direction, visual treatment, and conversion rationale for each block.

---

## Table of Contents

1. Design Goals & Principles
2. Page Structure Overview
3. Section-by-Section Breakdown
4. Visual Design System (Landing-Specific)
5. Copywriting Guidelines
6. Mobile Considerations
7. SEO & Technical Foundations
8. Accessibility Considerations
9. Analytics & Tracking Events
10. Conversion & A/B Testing Ideas
11. What to Avoid

---

## 1. Design Goals & Principles

A landing page has one job: get a visitor to sign up with the least friction possible. Everything below is designed around that, borrowing the same inspiration sources already established for the product (`TalkFiesta.md` Section 12):

| Principle | Why |
|---|---|
| **One clear primary action** | Every section should point back to "Start for Free" — no competing CTAs |
| **Show, don't just tell** | Visuals of the actual product (mock screenshots, not stock photos) build more trust than adjectives |
| **Address skepticism early** | "Is this just another language app that doesn't work?" — answer this before they even think it |
| **Energetic but credible** | Duolingo's playfulness + Babbel's professional polish — fun without looking unserious for adult learners |
| **Fast load, minimal friction** | No forced video autoplay, no heavy unoptimized assets — every extra second of load time costs conversions |

---

## 2. Page Structure Overview

```
┌─────────────────────────────────────────────┐
│ 1. Navigation Bar (sticky)                     │
├─────────────────────────────────────────────┤
│ 2. Hero Section                                  │
├─────────────────────────────────────────────┤
│ 3. Trust Bar (social proof strip)                  │
├─────────────────────────────────────────────┤
│ 4. Problem/Agitation Section                         │
├─────────────────────────────────────────────┤
│ 5. Three Pillars Section (Speaking/Vocab/Writing)      │
├─────────────────────────────────────────────┤
│ 6. Product Showcase (screenshots/mock UI, per pillar)    │
├─────────────────────────────────────────────┤
│ 7. How It Works (3-4 steps)                                │
├─────────────────────────────────────────────┤
│ 8. The 21-Day / 5-Cycle System Explainer                      │
├─────────────────────────────────────────────┤
│ 9. AI Differentiator Section                                     │
├─────────────────────────────────────────────┤
│ 10. Testimonials / Social Proof                                     │
├─────────────────────────────────────────────┤
│ 11. Comparison Table (vs. generic apps)                                │
├─────────────────────────────────────────────┤
│ 12. Pricing Section (full tiers, not just a teaser)                        │
├─────────────────────────────────────────────┤
│ 13. FAQ Section                                                             │
├─────────────────────────────────────────────┤
│ 14. Final CTA Section                                                          │
├─────────────────────────────────────────────┤
│ 15. Footer                                                                        │
└─────────────────────────────────────────────┘
```

**Design rationale for this order:** Follows a classic AIDA-plus-proof structure — grab Attention (hero), build Interest (problem → pillars), show credibility (product showcase, AI differentiator, testimonials), remove objections (comparison, FAQ), then Drive action (final CTA). Nothing asks for the sale until trust has been built.

---

## 3. Section-by-Section Breakdown

### 3.1 Navigation Bar (Sticky)

```
[🎉 TalkFiesta Logo]    Features   How It Works   Pricing        [Log In]  [Get Started →]
```

- **Sticky on scroll**, but shrinks slightly (reduce height by ~20%) once scrolled past the hero, so it doesn't dominate the viewport on mobile
- **Get Started** button is always the visually dominant element in the nav — orange fill, everything else is text/ghost style
- On mobile: collapses to logo + hamburger menu + a persistent "Get Started" button (never hide the primary CTA behind the hamburger)

---

### 3.2 Hero Section

```
┌───────────────────────────────────────────────────────┐
│                                                             │
│   [Small eyebrow tag: "AI-Powered English Learning"]          │
│                                                                   │
│   Master English in 21 Days                                        │
│   (Large, bold, Playfair Display, 2 lines max)                        │
│                                                                           │
│   Speaking. Vocabulary. Writing. One AI coach,                             │
│   real feedback, real progress — every single day.                           │
│                                                                                   │
│   [ 🚀 Start for Free ]   [ ▶ Watch 60-sec Demo ]                                   │
│                                                                                         │
│   ✓ No credit card required   ✓ Takes 5 minutes to start                                 │
│                                                                                               │
│                    [Hero visual: animated/static mockup of the                                  │
│                     Speaking exercise screen mid-feedback, showing                                │
│                     a real score and transcript — not a generic                                     │
│                     illustration]                                                                     │
└───────────────────────────────────────────────────────┘
```

**Why the hero visual should be a real product screenshot, not an illustration:** Generic "people talking with speech bubbles" stock-style illustrations are what every competitor uses and register as noise. A real mockup showing an actual score (e.g., "Fluency: 82") and real transcript with a highlighted correction communicates "this is a real, working, specific product" far faster than decorative art.

**Copy notes:**
- Headline stays outcome-focused ("Master English") not feature-focused ("AI Speaking Practice App")
- Subheadline is where the three pillars get named — this is the first time the visitor learns what's actually inside
- The two trust micro-copy lines under the buttons ("No credit card," "5 minutes to start") exist specifically to pre-empt the two most common signup hesitations

---

### 3.3 Trust Bar (Social Proof Strip)

A thin, understated strip directly below the hero — not flashy, just quietly credible:

```
Trusted by learners preparing for   [IELTS icon]  [TOEFL icon]  [Job Interviews icon]  [Business English icon]
```

or, once you have real numbers:

```
🔥 10,000+ learners   ⭐ 4.8 average rating   🌍 40+ countries
```

**Design note:** Keep this monochrome/muted (grayscale icons, small text) — it should feel like a quiet credibility signal, not compete visually with the hero above it.

---

### 3.4 Problem/Agitation Section

This section exists to make the visitor nod along before you present the solution — a classic conversion pattern most competitor landing pages skip by jumping straight to features.

```
┌───────────────────────────────────────────────────────┐
│         Sound familiar?                                     │
│                                                                 │
│   😕 "I understand English perfectly but freeze up when          │
│       I actually have to speak."                                    │
│                                                                         │
│   😕 "I've downloaded 5 apps and quit all of them within a week."       │
│                                                                             │
│   😕 "I don't know if I'm actually improving or just doing exercises."       │
│                                                                                 │
│              That's exactly what TalkFiesta fixes.                                │
└───────────────────────────────────────────────────────┘
```

**Design treatment:** Three short pain-point cards, casual/conversational tone (deliberately more informal than the rest of the page — this is the one section that should sound like a friend, not a product). Ends with a single bold line transitioning into the solution.

---

### 3.5 Three Pillars Section

```
┌────────────┐  ┌────────────┐  ┌────────────┐
│     🎤        │  │     📚        │  │     ✍️        │
│  Speaking       │  │  Vocabulary     │  │  Writing        │
│                   │  │                   │  │                   │
│  Real conversations │  │  210 words per      │  │  Daily prompts       │
│  with AI, public      │  │  cycle, retained       │  │  graded on grammar,     │
│  speaking practice,      │  │  through smart            │  │  structure &                │
│  even mock interviews.     │  │  spaced repetition.           │  │  vocabulary — with               │
│                               │  │                                   │  │  real, actionable feedback.        │
└────────────┘  └────────────┘  └────────────┘
```

**Design treatment:** Equal-weight 3-column grid (stacks vertically on mobile). Each card uses one of your three module colors as a subtle accent (top border or icon background) so visitors start associating color with module even this early. Icons should be simple line/duotone style, not literal clipart.

---

### 3.6 Product Showcase (Per Pillar)

For each of the 3 pillars, one larger, alternating-side section showing an actual screen from that module:

```
┌───────────────────────────────────────────────────────┐
│  [Text block, left]              [Screenshot, right]        │
│                                                                  │
│  Speak with confidence,             [Mockup: Speaking exercise    │
│  not just correctness                 screen, mic active, live      │
│                                          waveform, timer visible]      │
│  Get instant feedback on fluency,                                        │
│  grammar, and even filler words.                                            │
│  Practice public speaking, mock                                                │
│  interviews, or just casual                                                        │
│  conversation — with an AI that                                                        │
│  actually listens.                                                                          │
│                                                                                                    │
│  [ Try Speaking Practice → ]                                                                          │
└───────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────┐
│  [Screenshot, left]              [Text block, right]        │
│  (alternates side for visual                                    │
│   rhythm as user scrolls)                                          │
└───────────────────────────────────────────────────────┘
```

**Why alternate left/right per section:** Pure visual rhythm — three sections all laid out identically starts to feel monotonous while scrolling; alternating keeps the eye engaged without changing the underlying content structure.

---

### 3.7 How It Works

A simple, linear 4-step visual — deliberately mirrors Duolingo's "make it look effortless" pattern:

```
①  Take a 5-minute       ②  Get your personal      ③  Practice 10-15       ④  Track real
   level check                21-day plan               min a day               progress
   [icon]                     [icon]                     [icon]                  [icon]
```

**Design treatment:** Horizontal on desktop, vertical stack on mobile, connected by a subtle dotted line or arrow between steps to reinforce "this is a simple sequence," not a list of unrelated features.

---

### 3.8 The 21-Day / 5-Cycle System Explainer

This is where you differentiate from "just another app with lessons" — the structured program *is* a selling point on its own, and deserves its own dedicated section rather than being buried in a bullet list.

```
┌───────────────────────────────────────────────────────┐
│           This isn't random practice.                       │
│           It's a real program.                                  │
│                                                                     │
│   [Visual: horizontal progress path showing               │
│    Foundation → Intermediate → Advanced → Expert → Master     │
│    with a small "you are here" marker style graphic,             │
│    similar visual language to Duolingo's "Path"]                    │
│                                                                             │
│   5 cycles. 21 days each. Every cycle gets harder as you do —                  │
│   so you're always being challenged, never bored, never lost.                       │
└───────────────────────────────────────────────────────┘
```

**Why this deserves its own section:** Most competitors (Duolingo, Babbel) present an endless, somewhat shapeless lesson list. A visible, named structure with a clear beginning, middle, and end (even though it can continue past Cycle 5 per your "infinite content" design) gives visitors a concrete mental model of commitment — "I know exactly what 21 days looks like" is more motivating than "there are lessons."

---

### 3.9 AI Differentiator Section

This is where you can afford to be more technical/impressive than the rest of the page — visitors self-select into caring about this detail, and it builds credibility with the more skeptical segment of your audience.

```
┌───────────────────────────────────────────────────────┐
│         Not a chatbot. A real AI coach.                      │
│                                                                     │
│   🎯 Real-time voice conversations — talk naturally,                 │
│       AI responds like a real person, not a script                     │
│                                                                             │
│   🎭 Multi-agent mock interviews — practice with an AI                       │
│       HR interviewer, technical interviewer, AND hiring manager                 │
│                                                                                     │
│   📊 Feedback that's actually specific — not "good job,"                             │
│       but exact grammar corrections, word choice upgrades,                             │
│       and a real fluency score                                                            │
└───────────────────────────────────────────────────────┘
```

**Design treatment:** Slightly darker/contrasting background than surrounding sections (signals "premium/technical" moment), each point paired with either a short looping video/GIF of that exact feature in action, or a static annotated screenshot.

---

### 3.10 Testimonials / Social Proof

```
┌────────────┐  ┌────────────┐  ┌────────────┐
│  "..." quote    │  │  "..." quote    │  │  "..." quote    │
│  — Name, context   │  │  — Name, context   │  │  — Name, context   │
│  (photo optional)     │  │  (photo optional)     │  │  (photo optional)     │
└────────────┘  └────────────┘  └────────────┘
```

**Important note for a pre-launch/early product:** If you don't have real testimonials yet, do NOT fabricate quotes — this violates basic trust and is easy for visitors to sense as generic/fake. Options instead:
- Skip this section entirely until you have real users
- Replace with a "Founder's Note" section (a short, honest paragraph about why you built this) — authenticity substitutes for social proof at the pre-launch stage
- Use early beta-tester feedback with permission, clearly labeled as "Beta tester feedback"

---

### 3.11 Comparison Table

```
                          TalkFiesta    Generic Apps
Real-time AI conversation      ✅              ❌
Multi-agent interview practice    ✅              ❌
Public speaking training             ✅              ⚠️ Limited
Structured 21-day program               ✅              ⚠️ Sometimes
Detailed writing feedback                  ✅              ❌
Spaced repetition vocabulary                  ✅              ✅
```

**Design note:** Keep this honest — mark things competitors genuinely do well (like spaced repetition, which Duolingo/Anki do fine) with a checkmark too. A comparison table that shows the competitor with zero strengths reads as obviously biased and undermines trust in the rest of the page.

---

### 3.12 Pricing Section

Unlike the teaser-only version, this should be a real, browsable section — pricing is one of the top 2-3 things visitors scroll to check before deciding to sign up, so burying it behind a "See Full Pricing" link on a separate page costs conversions. Show it directly on the landing page.

```
┌───────────────────────────────────────────────────────┐
│                  Simple, honest pricing                     │
│              Start free. Upgrade when you're ready.             │
│                                                                     │
│            [ Monthly ]   ⚪──●  [ Annual — save 20% ]                  │
│                                                                           │
│  ┌──────────────────┐        ┌──────────────────┐                        │
│  │      FREE            │        │      PRO   ⭐ Popular   │                        │
│  │                          │        │                          │                        │
│  │      $0 / forever            │        │      $X / month             │                        │
│  │                                  │        │      billed annually            │                        │
│  │  ✓ 1 full cycle (21 days)            │        │  ✓ All 5 cycles, unlocked          │                        │
│  │  ✓ Daily vocabulary                      │        │  ✓ Everything in Free                  │                        │
│  │  ✓ Daily writing prompts                     │        │  ✓ Real-time AI conversation               │                        │
│  │  ✓ Basic speaking exercises                      │        │  ✓ Multi-agent mock interviews                 │                        │
│  │  ✓ Progress tracking                                 │        │  ✓ Unlimited document chat (RAG)                    │                        │
│  │  ✗ Real-time AI conversation                             │        │  ✓ Priority AI feedback (faster)                        │                        │
│  │  ✗ Mock interview panel                                     │        │  ✓ Downloadable progress reports                            │                        │
│  │  ✗ Document chat (RAG)                                          │        │                                                                   │                        │
│  │                                                                        │        │                                                                   │                        │
│  │      [ Start Free → ]                                                     │        │      [ Start Pro Trial → ]                                            │                        │
│  └──────────────────┘        └──────────────────┘                        │
│                                                                                 │
│              All plans include a 7-day money-back guarantee                       │
└───────────────────────────────────────────────────────┘
```

**Design rationale for the structure:**
- **Only 2 tiers, not 3+** — a Free/Pro/Enterprise-style 3-tier table is standard for B2B SaaS, but for a consumer app, more than 2 visible options tends to increase decision paralysis rather than upsell; keep it to a clear binary choice
- **Pro tier is visually emphasized** ("Popular" badge, slightly larger card, or a subtle border glow) — this is standard pricing-page psychology; anchoring attention on the plan you actually want most people to choose
- **Monthly/Annual toggle** — showing the annual discount clearly (e.g., "save 20%") nudges toward the higher-LTV choice without hiding the monthly option from people not ready to commit
- **What's crossed out on Free matters as much as what's included** — explicitly showing "✗ Real-time AI conversation" on the Free tier (rather than just omitting it) makes the upgrade value concrete instead of vague

**Founding Member / Early-Bird angle (ties back to the testimonials gap in Section 3.10):**

Since TalkFiesta is pre-launch without social proof yet, consider a limited-time **Founding Member offer** directly in this section — e.g., "First 500 users lock in Pro pricing for life at $X" — this does double duty:
- Creates urgency/scarcity that substitutes for the trust signal testimonials would normally provide
- Directly incentivizes the early signups you need in order to *generate* those future testimonials

```
┌───────────────────────────────────────────────────────┐
│   🎉 Founding Member Offer — First 500 users only            │
│   Lock in Pro for $X/mo for life (regular price will be $Y)     │
│   [ 342 / 500 spots claimed ]  (progress bar, if genuinely true)   │
└───────────────────────────────────────────────────────┘
```

**Important honesty note:** Only show a claimed-spots counter or countdown if it's genuinely real and dynamically accurate — a fake/static scarcity counter is one of the most commonly called-out dark patterns, and it actively damages trust with the exact skeptical, detail-oriented audience segment (people learning English for career/exam purposes) most likely to notice and be put off by it.

**Pricing FAQ micro-copy directly below the cards** (short, not the full FAQ accordion):
- "Can I switch plans later?" — Yes, anytime
- "What happens to my progress if I downgrade?" — Your progress is always saved; you just lose access to Pro-only features
- "Is there a student discount?" — (if applicable)

---

### 3.13 FAQ Section

Standard accordion-style FAQ addressing the specific objections your product will face:

- "Is this better than [Duolingo/Babbel/etc.]?"
- "Do I need to already speak some English to start?"
- "How does the AI actually give feedback?"
- "Is my voice/data private?"
- "Can I cancel anytime?"
- "What if I miss a day — do I lose my streak/progress?"

**Design treatment:** Collapsed by default, one open at a time, simple +/− icon toggle — no need for anything fancier than a clean accordion here.

---

### 3.14 Final CTA Section

```
┌───────────────────────────────────────────────────────┐
│                                                             │
│          Your English is about to get a lot better.           │
│                                                                   │
│                  [ 🚀 Start Your First Day Free ]                    │
│                                                                         │
│              Join in under 5 minutes. No credit card.                    │
│                                                                               │
└───────────────────────────────────────────────────────┘
```

**Design treatment:** Full-width, high-contrast background (brand green or a gradient), the single largest CTA button on the entire page. This is the last chance — no secondary links, no navigation distractions, just the one action.

---

### 3.15 Footer

```
[Logo]  TalkFiesta

Product          Company         Legal              Connect
Features           About            Privacy Policy      Twitter/X
Pricing             Blog             Terms of Service    Instagram
How It Works       Contact          Cookie Policy         LinkedIn

© 2026 TalkFiesta. All rights reserved.
```

Standard, unremarkable footer — footers are not where visitors make decisions, so keep it clean and functional rather than creative.

---

## 4. Visual Design System (Landing-Specific)

Reuses the brand system already established in `TalkFiesta.md` and the Phase 1 design flow, with landing-specific emphasis:

| Element | Treatment |
|---|---|
| **Primary color (Green #1A6B45)** | Used for the majority of the page — nav, section headers, secondary buttons |
| **Accent color (Orange #F4832A)** | Reserved almost exclusively for CTA buttons — this scarcity is deliberate, so the eye is trained to associate orange = "click here" throughout the whole page |
| **Typography** | Playfair Display for section headlines (adds warmth/personality), Inter/DM Sans for body copy and UI mockups |
| **Whitespace** | Generous — landing pages that feel cramped read as low-quality/low-trust; err toward more breathing room than feels necessary |
| **Motion** | Subtle scroll-triggered fade/slide-ins for each section (nothing aggressive), a looping micro-animation in the hero (e.g., waveform pulsing) to signal "this is a live, dynamic product" |
| **Screenshots/mockups** | Always framed in a simple device/browser chrome, never floating raw — reinforces "this is a real, polished app" |

---

## 5. Copywriting Guidelines

- **Headlines:** Outcome-first, not feature-first ("Master English" not "AI Speaking Feature")
- **Body copy:** Short sentences, second person ("you"), active voice
- **Numbers over adjectives:** "210 words per cycle" beats "tons of vocabulary"; "Fluency: 82/100" beats "detailed feedback"
- **Avoid superlatives without proof:** "The best English app" is a claim nobody believes from a landing page alone — let the comparison table and specific features make that case instead
- **CTA button copy:** Vary slightly by section to match context ("Start for Free" in hero, "Try Speaking Practice" in the showcase section, "Start Your First Day Free" in the final CTA) rather than robotically repeating the identical phrase everywhere

---

## 6. Mobile Considerations

- Hero CTA button should be reachable **without scrolling** on a typical mobile viewport — keep the hero compact enough that "Start for Free" is visible on load, not below the fold
- Product showcase sections (3.6) stack screenshot-above-text on mobile, not side-by-side
- Comparison table (3.11) needs a mobile-friendly format — either horizontal scroll or convert to a stacked card-per-feature layout rather than a cramped tiny table
- Pricing cards (3.12) stack vertically on mobile, Pro card first (not Free) if it's the recommended plan — don't make mobile visitors scroll past Free to discover Pro exists
- Sticky nav should shrink more aggressively on mobile to preserve vertical space for content
- **Persistent bottom CTA bar on mobile:** once the visitor scrolls past the hero, show a slim, sticky bottom bar with just a "Get Started" button — mobile visitors lose the hero's CTA from view almost immediately after scrolling, and re-showing it in a low-profile persistent bar recovers conversions that would otherwise require scrolling all the way back up or down to the final CTA

---

## 7. SEO & Technical Foundations

Easy to overlook in a pure design spec, but a landing page that looks great and never gets found converts zero visitors. Baseline requirements:

| Item | Detail |
|---|---|
| **Title tag** | Specific and keyword-relevant, not just the brand name — e.g. "TalkFiesta — AI English Speaking, Vocabulary & Writing Practice" rather than just "TalkFiesta" |
| **Meta description** | One compelling sentence under ~160 characters — this is effectively free ad copy shown directly in search results |
| **Open Graph / Twitter Card image** | A custom-designed image (not a random screenshot) for when the link is shared on social/messaging apps — this single asset affects click-through rates on every shared link |
| **Semantic HTML structure** | One `<h1>` (the hero headline), proper `<h2>`/`<h3>` hierarchy for section headers — helps both SEO crawlers and screen readers (ties into Section 8) |
| **Page speed** | Target a Largest Contentful Paint under ~2.5s — compress/lazy-load all screenshots below the fold, serve the hero image in a modern format (WebP/AVIF) |
| **Structured data (Schema.org)** | Use `SoftwareApplication` or `Organization` markup where relevant — helps search engines display rich results (ratings, pricing) directly in search listings |
| **Sitemap & robots.txt** | Standard, but easy to forget on initial launch — make sure the landing page and any public blog/help content are actually crawlable |
| **Canonical URL** | Especially relevant once pricing/FAQ live on both the landing page and dedicated sub-pages, to avoid duplicate-content SEO issues |

---

## 8. Accessibility Considerations

TalkFiesta's own audience — English learners, some of whom may have varying levels of comfort with technology or assistive needs — makes this more than a checkbox concern.

- **Color contrast:** Verify the green/orange palette meets WCAG AA contrast ratios, especially orange CTA text/background combinations, which are a common accessibility failure point for brand-colored buttons
- **Alt text on all images/screenshots:** Especially the hero product mockup — a screen-reader user should still understand what the product does from the alt text alone
- **Keyboard navigability:** Every interactive element (nav links, accordion FAQ, pricing toggle, CTA buttons) must be reachable and operable via keyboard alone, with visible focus states
- **No motion-only communication:** If the hero uses a subtle waveform animation (Section 4), make sure the same information isn't lost for users with `prefers-reduced-motion` enabled — respect that setting and fall back to a static version
- **Captions/transcripts for any demo video:** The "Watch 60-sec Demo" hero button (Section 3.2) should link to a video with captions, not just raw audio — doubly relevant given the product itself is about spoken English
- **Form labels:** Any embedded email capture or waitlist form (Section 10 below) needs properly associated `<label>` elements, not just placeholder text as the only label

---

## 9. Analytics & Tracking Events

What to actually measure once this page is live — without this, none of the A/B testing ideas in Section 10 are possible:

| Event | Why It Matters |
|---|---|
| `hero_cta_click` vs `final_cta_click` vs `nav_cta_click` | Tells you WHICH placement of the primary CTA is actually driving signups — informs whether sections in between are helping or just adding scroll fatigue |
| `demo_video_play` | Signals genuine interest even from visitors who don't convert immediately — useful for retargeting |
| `pricing_toggle_switch` (monthly → annual) | Measures whether the annual discount framing is actually landing |
| `faq_item_expand` (per question) | Reveals which objections visitors actually have — if one FAQ question gets opened far more than others, that's a signal that concern deserves to be addressed earlier/more prominently on the page, not buried in an accordion |
| Scroll depth (25%/50%/75%/100%) | Identifies where visitors are dropping off — if most visitors never reach the Pricing section, that's a structural problem worth knowing before running any copy-level A/B tests |
| `signup_started` vs `signup_completed` | Distinguishes "clicked Get Started" from "actually finished the form" — a big gap between these two numbers points to friction in the signup flow itself, not the landing page |

---

## 10. Conversion & A/B Testing Ideas

Once the page is live, worth testing (don't try to guess the winner upfront — these are genuinely uncertain):
- Hero headline: outcome-focused ("Master English in 21 Days") vs. pain-focused ("Stop Freezing Up When You Speak English")
- CTA copy: "Start for Free" vs. "Take the Free Level Test" (the latter reduces perceived commitment — a test feels lower-stakes than "starting" a program)
- Hero visual: static screenshot vs. short autoplay-muted looping video of the Speaking feedback screen in action
- Presence/absence of the Problem/Agitation section (3.4) — some audiences respond well to it, others find it presumptuous
- Pricing section: showing the Founding Member offer prominently vs. a plain standard Free/Pro table — worth confirming urgency-driven framing actually outperforms a straightforward one for this specific audience, rather than assuming it will

---

## 11. What to Avoid

- ❌ Stock photos of generic "diverse people smiling at laptops" — reads as template/generic instantly
- ❌ Fabricated testimonials or fake user counts before you have real ones
- ❌ A fake or static "spots remaining" counter on the Founding Member offer (Section 3.12) — if you show a claimed-spots number, it must be real and genuinely updating
- ❌ More than one primary CTA style competing for attention in the same viewport
- ❌ Autoplaying audio (extremely common trust-killer, especially ironic for a *speaking* app — never auto-play sound)
- ❌ A wall of text before the first visual — visitors should see product evidence within the first screen, not just words
- ❌ Comparison tables that make competitors look artificially bad (undermines credibility of the whole page)
- ❌ Hiding pricing behind a separate page/link when visitors are actively looking to compare Free vs Pro on this page (Section 3.12) — the friction of an extra click at this exact decision point costs more conversions than it seems

---

**Project:** TalkFiesta
**Document:** Landing Page Design
**Companion to:** `TalkFiesta.md`
**Status:** Ready for visual design / frontend implementation
