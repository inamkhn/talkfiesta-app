# TalkFiesta — Frontend UX/UI Design Specification

**Scope:** Landing Page → Pricing/Payment → Registration/Login → First-Time Onboarding → Initial CEFR Assessment → Assessment Results → Learning-Plan Handoff  
**Version:** V4 · Frontend Design Proposal  
**Status:** Design specification only — no code, no implemented payment system implied  
**Product:** TalkFiesta, AI-powered English learning platform  
**Intended handoff:** Product designer, UX designer, frontend engineer, product owner

---

## 1. Product context and scope

TalkFiesta helps learners improve three English-language skills: **Speaking**, **Vocabulary**, and **Writing**. A first-time learner chooses goals and preferences, takes a short assessment, receives a **provisional** CEFR placement, and begins a personalized 21-day learning journey. Learning modules progress independently and AI feedback supports later practice.

This document defines the learner-facing **design**, visual hierarchy, page content, states, user interactions, and responsive behavior from the public landing page through the first assessment result. It intentionally does **not** contain application code, component implementation, database definitions, API payloads, or payment integration instructions.

### Source-aligned features

- Email and Google authentication.
- Learning goals: fluency, business/professional English, exams, and travel.
- Preferences: focus skills, available daily time, preferred topics, and comfort speaking English.
- Assessment activities: adaptive grammar questions, vocabulary/comprehension questions, a writing response, and an optional recorded speaking response.
- OpenAI-assisted speaking transcription and writing/speaking feedback behind the scenes; this is reflected only in learner-facing states and explanations.
- Provisional CEFR result, skills summary, strengths, areas to improve, and personalized learning-plan handoff.
- Brand direction from the original product concept: energetic but clean, green + orange, rounded cards and limited celebratory motion.

### Newly proposed in this document

- **Landing-page pricing section and a payment/checkout journey.** Subscription tiers, exact prices, currency, supported payment methods, refund rules, and entitlement gates were **not defined** in the earlier TalkFiesta product documents. All pricing UX here is a **design proposal, not an established business commitment**.
- Optional plan selection before signup; users may complete an introductory assessment without entering a payment method (recommended product policy, subject to approval).
- Form field microcopy, layouts, empty/error states, and accessibility specifications.

### Design goals

1. Explain the product within the first visible screen.
2. Offer a clear path to start learning, even before the learner chooses a paid plan.
3. Make subscription pricing transparent without distracting from the learning mission.
4. Complete onboarding in a few small steps instead of one long form.
5. Make an assessment feel friendly, credible, and low pressure.
6. Support interruptions, device changes, microphone denial, and slow AI processing.
7. Explain placement accurately: **provisional estimate**, not an official CEFR certificate.

---

## 2. Information architecture and navigation

### Public pages

| Page | Recommended route label | Primary purpose |
|---|---|---|
| Landing | Home | Explain TalkFiesta, benefits, learning modules, process, pricing, FAQ |
| Pricing section | Pricing anchor on Home | Compare plans and select a billing option |
| Sign up | Create Account | Email/password or Google signup |
| Sign in | Welcome Back | Authenticate existing learner |
| Password recovery | Reset Password | Recover an email/password account |
| Checkout (proposed) | Secure Checkout | Finalize selected subscription with a payment provider |
| Checkout outcome (proposed) | Payment Confirmation | Clearly show success, pending, canceled or failure state |

### Authenticated onboarding pages

| Screen | Navigation label | Primary purpose |
|---|---|---|
| Goal selection | Your Goals | Identify desired English outcomes |
| Preferences | Your Learning Style | Select skill focus, practice time, topics and self-reported comfort |
| Assessment intro | Discover Your Level | Explain duration, exercise types, recording, and optional microphone |
| Grammar | Grammar | Present a small adaptive set of questions |
| Vocabulary/comprehension | Vocabulary | Test words-in-context and short comprehension |
| Writing | Writing | Capture a short original answer |
| Speaking | Speaking | Capture, preview, re-record, or skip a short audio response |
| Processing | Preparing Your Results | Indicate AI scoring activity and safe leave/return behavior |
| Results | Your Starting Level | Explain provisional CEFR placement and skill evidence |
| Plan preview | Your First Learning Plan | Preview Day 1 and continue to dashboard |

**Routing principle:** The learner’s server-saved onboarding state governs which step is accessible. Browser back/refresh must not erase completed inputs or create duplicate assessments.

### Primary user paths

**Path A — Start learning:** Landing → Sign up/login → Goals → Preferences → Assessment → Results → Plan Preview → Dashboard.

**Path B — Browse pricing first:** Landing → Pricing → Choose plan → Sign up/login if needed → Return to selected plan → Checkout (if paid) → Continue or resume onboarding. Payment is independent of assessment completion.

**Path C — Returning learner:** Sign in → If onboarding incomplete, resume correct step; otherwise go to Dashboard.

**Path D — Interrupted assessment:** Sign in → Resume assigned question or processing screen; never restart a valid attempt without clear consent.

---

## 3. Visual language and design system

### Brand personality

**Friendly, confident, encouraging, modern, and professional.** The experience should appeal to students and working professionals; avoid childish illustrations or noisy gamification on assessment screens.

| Element | Design direction |
|---|---|
| Primary color | Rich growth green; recommended exploration: `#178467` |
| Accent color | Warm celebratory orange; recommended exploration: `#F59E42` |
| Background | Warm off-white or very light gray |
| Surface | White cards, subtle borders, soft shadows |
| Headings | Dark charcoal for reliable contrast |
| Positive state | Deep accessible green with icon + text |
| Warning state | Amber with readable warning copy |
| Error state | Red with specific actionable guidance, never color alone |
| Corners | Rounded cards and controls; moderately rounded rather than pill-shaped everywhere |
| Illustration style | Clean contextual learning scenes, simple abstract language motifs, restrained character use |
| Motion | Short transitions, subtle progress transitions, optional celebration after a completed milestone |

The hex values are **starting design tokens to verify in accessibility reviews**, not a finalized brand palette. Verify contrast for all text/buttons.

### Typography and spacing

- Headings: contemporary humanist/geometric sans-serif, e.g. **Manrope** or similar.
- Body: legible sans-serif, e.g. **Inter** or similar.
- Responsive type: strong headline on desktop, shorter wrapping and adequate line height on mobile.
- Prefer a clear 8-point spacing rhythm with generous whitespace.
- Limit text width in forms and assessment tasks to improve reading comfort.
- Use card grouping and section separation rather than excessive decorative borders.

### Core interaction patterns

- One strong primary CTA per screen; one clearly distinguishable secondary action if needed.
- Persistent progress on onboarding and assessment; never show a fabricated precise percentage for a variable-length adaptive test.
- Autosave visual states: **Saving… → Saved** and explicit retry on failure.
- Native keyboard/focus behavior for forms, radio groups, and checkboxes.
- Inline validation beside the relevant field.
- State labels use plain English, e.g. **Evaluating your writing**, not internal names like `PROCESSING`.

---

## 4. Landing page — section-by-section design

### 4.1 Global public header

**Desktop:** TalkFiesta logo left; navigation centered/right: **How It Works, Learning Skills, Pricing, FAQs**; secondary **Log in**; prominent **Get Started** button. Sticky header after scroll with lighter background and visible focus behavior.

**Mobile:** Logo + Log in + accessible menu button; menu expands to the same anchor links and a primary Get Started CTA. Ensure menu and sticky header do not obscure anchor headings.

### 4.2 Hero — first viewport

**Headline (example):** “Speak English with confidence. One day at a time.”

**Supporting copy:** “Practice speaking, build vocabulary, and improve writing with personalized English exercises and clear AI feedback.”

**Primary CTA:** **Start My English Journey**  
**Secondary CTA:** **See How It Works**

**Confidence strip:** “Personalized 21-day learning cycles · Speaking, Vocabulary & Writing · Feedback after practice.”

**Hero visual:** A product-style composite illustrating three authentic app moments: a speaking microphone/recording card, a vocabulary flashcard, and a writing correction card. Any sample score must be visibly marked as an example. Do not use fake testimonials or unverified improvement percentages.

**Layout:** Two columns on desktop (copy left, application preview right); copy, CTA, then preview on mobile.

### 4.3 “Why TalkFiesta?” value proposition

Three benefit cards:

1. **Practice with purpose:** Follow short, goal-based activities rather than random exercises.
2. **Get feedback you can use:** See specific language corrections and next steps.
3. **See your growth:** Track activities, vocabulary reviews, and skill trends.

Use recognizable icons and one illustrative screenshot per benefit if visual assets are available.

### 4.4 Three learning pillars

A set of three equal-height cards with an illustrative UI preview each:

| Card | Value message | Key visible example | CTA |
|---|---|---|---|
| Speaking | “Talk more naturally.” | Mic, prompt, transcript corrections | Explore Speaking |
| Vocabulary | “Learn words that stick.” | Definition, example, review due indicator | Explore Vocabulary |
| Writing | “Make every sentence clearer.” | Inline correction and revised sentence | Explore Writing |

CTA scrolls to explanation or begins signup; don't route to private lesson screens for logged-out users without a clear sign-in handoff.

### 4.5 “How it works” — learning journey

Four numbered visual steps:

1. **Choose your goals** — business, travel, everyday English, or exams.
2. **Discover your starting level** — quick language assessment; speaking is optional.
3. **Get your learning plan** — a 21-day cycle aligned to your goals.
4. **Practice and improve** — clear feedback, independent module progress.

A simple horizontal timeline becomes a stacked vertical stepper on mobile.

### 4.6 Personalized practice showcase

A large mock dashboard panel, clearly marked **Example**. Show a learner with a provisional A2 placement, a 15-minute target, and example Day 1 activities:

- Speaking — “Introduce yourself at work.”
- Vocabulary — “10 useful workplace words.”
- Writing — “Write a short professional introduction.”

Emphasize that activities are adapted to preferences and curriculum level, not generated unreliably in the browser.

### 4.7 Friendly AI feedback section

Show an **example** transformation: 

- Learner phrase: “Yesterday I go to office.”
- Suggested improvement: “Yesterday I went to the office.”
- Short tip: “Use past tense when describing completed actions.”

Label the example as illustrative. Explain that feedback is generated after submission and processing may take time. Avoid promises that automated evaluation is infallible or CEFR-certified.

### 4.8 Trust, privacy and credibility section

Include accurate, maintained information only:

- Audio is used to support speaking exercises and evaluations.
- Learners can control microphone permission at the browser level.
- Provide links to the real privacy policy, terms, and audio retention explanation once approved.
- If the product has no verifiable adoption numbers or testimonials, do **not** invent “10,000+ learners,” five-star ratings, or famous brand logos.

**Recommendation:** A small product privacy explanation is better than unverifiable trust badges.

---

## 5. Landing-page pricing and payment section (new proposal)

### 5.1 Section objective

Help visitors understand the commercial model **before signup**, compare features transparently, and start checkout without ambiguity. Pricing should live on the landing page itself, not only on a separate hidden route.

**Section heading (example):** “Choose the way you want to learn.”  
**Subheading:** “Start with a level assessment, then choose the learning experience that fits your goals.”

### 5.2 Recommended pricing presentation

**Two tiers are the simplest initial design:**

| Pricing card | Free / Starter (proposed) | Plus / Premium (proposed) |
|---|---|---|
| Price | **[Confirm free policy]** | **[Insert approved price and currency]** |
| Assessment | Basic starting-level assessment | Same assessment; no implication of better grading |
| Learning access | **[Define actual starter access]** | **[Define purchased learning entitlements]** |
| Feedback usage | **[Define truthful limits]** | **[Define truthful limits]** |
| Speaking recording limits | **[Define usage limits]** | **[Define usage limits]** |
| Writing revisions | **[Define usage limits]** | **[Define usage limits]** |
| Billing | No card if free tier is approved | Monthly or yearly if commercially approved |
| Main CTA | Start Learning | Choose Plus |

**Do not show made-up prices, discounts, trials, premium capabilities, or unlimited AI usage.** The product owner must approve each row before publishing the landing page.

### 5.3 Pricing UI composition

- One consistent pricing section at the landing page's Pricing anchor.
- Two plan cards side by side on desktop and stacked on mobile.
- Clear plan name, final approved displayed price, billing period, included features, usage limits, and exclusions.
- Paid card may have a discreet “Recommended for regular practice” annotation **only if justified as editorial guidance**, not a fabricated popularity claim.
- Monthly/annual segmented selector **only if both plans are actually sold**; show exactly how annual billing is charged (e.g., total annual charge) and any approved discount.
- Tax/currency disclosure beside the displayed amount as required by actual markets and payment provider.
- A short comparison link or expandable feature table beneath the cards.
- FAQ just below pricing addressing renewal, cancellation, assessment access, payment security, and refunds—only with approved policy text.

### 5.4 Recommended conversion policy

**Default recommendation:** Allow visitors to sign up, complete onboarding, and view their **provisional assessment result without payment**. Present a paid plan as an optional choice before or after the assessment, rather than blocking the user midway through a speaking recording.

This is a UX recommendation. If TalkFiesta is explicitly a paid-first product, the product owner must approve a different gate and clearly communicate it **before** the user starts assessment.

### 5.5 Pricing CTA behavior

| Visitor action | Expected UI behavior |
|---|---|
| Click **Start Learning** on Free | Go to registration; preserve intended free selection |
| Click **Choose Plus** when logged out | Go to registration/login; preserve chosen paid tier and period |
| Click **Choose Plus** when logged in | Open payment confirmation/checkout step |
| Already subscribed clicks paid CTA | Show current plan and manage-billing path; avoid duplicate purchase |
| Returns from canceled checkout | Explain no charge was completed and offer retry or free continuation |
| Returns from pending payment | Explain payment is pending verification; do not unlock paid content based only on browser redirect |

### 5.6 Payment / checkout experience

**Recommendation:** The landing page contains **pricing and purchase CTAs**, while actual card collection happens on a secure hosted checkout from the selected payment provider. Do not embed a homemade raw-card form on the landing page.

**Checkout UX stages:**

1. **Review order:** selected plan, billing cadence, approved price, currency, applicable taxes, renewal terms, next charge date if applicable.
2. **Authenticate:** sign in or create account if needed, without losing the selected plan.
3. **Secure payment:** transfer to hosted payment provider. Supported methods appear only after confirming provider/region support.
4. **Payment verification:** return to TalkFiesta; show verifying state while the backend confirms the provider's payment event.
5. **Outcome:** success, pending, canceled, or failed, each with a specific next action.

**Success screen:** plan name, billing cadence, receipt/invoice link if available, access status, next step **Continue Learning** or **Begin Assessment**.

**Failure screen:** clear failure message, safe **Try Again** action, contact support link and a route back to learning without an accidental duplicate charge.

**Payment and commercial decisions still required:** exact product tiers, currency/geographies, subscription vs one-time billing, discounts, trial availability, tax handling, refund policy, cancellation behavior, purchased entitlement limits, payment provider, invoicing, legal copy and billing data storage. These are outside the current 14-table V4 learner schema and require a separate billing-domain design when chosen.

---

## 6. Landing-page footer

Organize into four compact groups: **Product** (Speaking, Vocabulary, Writing, How It Works), **Explore** (Pricing, FAQs), **Support** (Help, Contact), and **Legal** (Privacy, Terms, Refund/Cancellation policy once approved).

Bottom line: TalkFiesta brand, copyright year maintained dynamically at implementation time, language preference if supported, and a minimal social-link row only for real channels.

---

## 7. Authentication experience

### 7.1 Sign up screen

**Layout:** Centered form card, generous whitespace, compact brand mark; desktop may have a companion panel describing the learning experience. On mobile, use a single focused column.

**Heading:** “Create your TalkFiesta account.”  
**Subheading:** “Your English journey starts here.”

**Fields:** Display name, email, password; optional confirm-password if desired. Clear password guidance and show/hide toggle.

**Primary CTA:** **Create Account**  
**Alternative:** **Continue with Google**  
**Footer:** Already have an account? **Log in**.

Show real terms/privacy links with user-friendly consent language; no prechecked marketing consent. Do not conflate a paid subscription with creating a free account.

**Key states:** initial, invalid fields, password too weak, email already used, pending request, account created, verification required (if implemented), OAuth error, rate-limited, offline.

**After success:** Restore selected pricing intention when present; otherwise continue to Goals.

### 7.2 Login screen

**Heading:** “Welcome back.”  
**Fields:** Email, password.  
**Actions:** Sign In, Continue with Google, Forgot Password, Create Account.

Upon success, route by saved onboarding status: Goals, Preferences/assessment, Processing/Results, or Dashboard. Avoid revealing sensitive account existence through password-reset messages.

### 7.3 Password recovery

- Enter email → generic “If this address is registered, we'll send instructions.”
- Link sent/success state → return to Login.
- Expired recovery link → offer resend safely.
- No dead-end screens.

---

## 8. First-time onboarding design

### Shared onboarding shell

A focused, distraction-free design distinct from marketing pages. Header: logo left, “Your learning setup” center or right, optional **Save & exit**. A two-step progress indicator for Goals and Preferences. No global marketing navigation during this flow.

**Desktop:** max-width centered content, approximately a comfortable reading column, choices displayed in 2-column selectable cards where appropriate.

**Mobile:** single-column cards and sticky bottom **Continue** CTA if it does not obscure content.

### 8.1 Screen 1 — Choose learning goals

**Heading:** “What would you like to achieve in English?”  
**Supporting text:** “Choose everything that matters to you. You can change this later.”

Selectable goal cards:

- **Business & professional English** — meetings, interviews, workplace communication.
- **Everyday fluency** — confident conversation and daily situations.
- **Travel & social communication** — airports, hotels, new people.
- **Exam preparation** — structured language practice; don't promise official exam scoring.

**Selection:** multi-select, at least one goal.  
**CTA:** **Continue**.  
**Empty validation:** “Choose at least one goal to continue.”

### 8.2 Screen 2 — Learning preferences

**Heading:** “Let's make your plan fit your life.”

**Sections within one short screen or internally grouped form:**

1. **Focus skills (multi-select):** Speaking & pronunciation; Vocabulary; Writing & grammar.
2. **Daily practice time (single-select):** 5, 10, 15, 30 minutes.
3. **Topics you enjoy (multi-select):** Daily life, Work, Travel, Technology, Culture; optionally Exams depending on goals.
4. **Speaking comfort (single-select):** Just starting; Simple conversations; Familiar topics confidently; Complex topics.
5. **Language/timezone (optional or background-prepopulated):** Native language for explanation context; time zone for streaks.

**CTA:** **Create My Assessment** or **Continue to Level Check**.  
**Secondary:** Back.

Example saved profile to illustrate the interface: Business goal, focus Speaking and Writing, 15 minutes/day, Daily life/Travel, comfort “I can manage simple conversations.” The backend uses this to start question selection, **not** as a verified CEFR score.

**States:** changing selections, inline constraints, saving, saved, failed save/retry, resumed with previous answers.

---

## 9. Assessment design principles

### Overall experience

**Tone:** “We're finding a good starting point—not grading your worth.” Keep language calm and nonjudgmental.  
**Estimated length:** approximately 5–7 minutes; clearly an estimate, not guaranteed.  
**Assessment format:** short adaptive grammar/vocabulary items, one writing task, optional speaking recording.

**Shared assessment shell:**

- Top: TalkFiesta mark, “English Level Check,” exit/save control.
- Compact segmented progress labeled **Grammar → Vocabulary → Writing → Speaking**; show “Speaking optional.”
- Question content center, with readable line lengths.
- Bottom: Back where permitted, **Continue/Save Answer**, responsive help/support.
- Indicate that answers are saved securely without exposing private answer keys.
- Avoid a ticking timer unless time limits are explicitly part of the measured skill; a total elapsed timer isn't necessary for MVP.
- Do not display immediate correctness, grades, or a provisional CEFR after each question—the selection is adaptive and such hints could bias future answers.

### Navigation behavior

- At most one unanswered assigned question remains active at a time (subject to actual assessment design).
- The assessment can have a variable question count, so progress should communicate stages rather than a misleading exact completion percentage.
- **Back** is possible within non-finalized steps if consistent with the saved attempt; if objective answers are intentionally frozen, explain that clearly.
- **Save & exit** leaves the assessment resumable, not submitted.
- Browser refresh restores the existing question, answer and stage.

---

## 10. Assessment screens in detail

### 10.1 Assessment welcome

**Heading:** “Let's discover your starting English level.”  
**Supporting text:** “A few short activities help us choose the right first lessons.”

Four informational mini-cards: Grammar, Vocabulary, Writing, Speaking (Optional).  
Duration: “Around 5–7 minutes.”  
Privacy note: “If you record audio, we'll use it to assess your spoken response. You can skip speaking.”  
Primary CTA: **Start Assessment**.  
Secondary link: **How will my result be used?** (opens a short clear explanation).

### 10.2 Grammar questions

**Example prompt:** “I have worked here ____ 2022.”

Choice cards: **For / Since / During**. One selection at a time.

**Interaction details:** Entire card is clickable; selected state uses border + check icon + distinct background; can move using keyboard; button enabled only after selection.

**Bottom CTA:** **Save & Continue**.  
**Progress note:** “We're adapting the next question to your answers.”

The number/difficulty of questions may change after each answer; show a stable section label rather than “question 2 of exactly 3” unless fixed.

### 10.3 Vocabulary and short comprehension

**Example passage:** “My flight was delayed, so we had to reschedule the meeting for Tuesday.”  
**Question:** “What does ‘reschedule’ mean?”

Three single-select options with enough vertical spacing. The sentence may be rendered inside a quiet highlight panel. Consider a separate reading-comprehension variation in the same section.

**UX:** No instant reveal of correct answer in assessment mode. Next question can adapt based on response.

### 10.4 Writing task

**Example prompt:** “Write a short message to a colleague about a trip you are planning. Say where you're going, why, and what you'll do there.”

**Suggested length:** 50–80 words for illustrative A2-oriented prompt; actual target follows the assigned task and level.  
**Editor:** plain-text multiline area (not rich-text), live word count, accessible helper text.  
**Actions:** Back, Save Draft, **Submit Writing & Continue**.

**Helpful affordances:** Prompt remains visible while editing; gentle word-count suggestion; saved indicator. No spelling correction that rewrites the learner's text automatically; evaluation must receive the learner's original expression. Do not display live AI writing grades during the assessment.

**Failure states:** draft saving interrupted → preserve local in-memory text if possible and show clear retry; if reloaded, restore last confirmed server save and warn about unsaved edits.

### 10.5 Speaking task — optional

**Heading:** “Tell us about yourself.”  
**Prompt (example):** “Introduce yourself to a new colleague. Say what you do, something you enjoy, and what you did yesterday.”

**Target:** 30–60 seconds.  
**Pre-record note:** “You can replay or re-record before submitting. Speaking is optional.”

**Recording UI layout:**

- Prompt card fixed near the top, readable during recording.
- Large central microphone button with accessible label **Start recording**.
- Recorder states: Ready → Requesting permission → Recording → Stopped → Uploading → Uploaded.
- During recording: elapsed seconds, waveform/volume indicator as decorative supplement, **Stop recording** button.
- After recording: playable audio with explicit **Play**, **Record again**, and **Use this recording** controls.
- **Skip for now** link with gentle explanation: “Your result will use the skills we could assess.”

**Microphone permission behavior:**

| State | Learner-facing message | Action |
|---|---|---|
| Permission not yet granted | “Allow microphone access to record your answer.” | Continue to browser permission |
| Permission denied | “We couldn't access your microphone.” | Try again or Skip |
| No microphone found | “No microphone is available on this device.” | Skip |
| Recording too short / silent | “We couldn't hear enough speech to evaluate this recording.” | Re-record or Skip |
| Upload interrupted | “Your recording wasn't uploaded. Try again.” | Retry upload safely |
| Upload confirmed | “Recording saved.” | Continue |

**Privacy details:** Before recording, link to the recording/privacy explanation. No automatic microphone activation on entry. No background recording. If audio cannot be evaluated reliably, show “Speaking not assessed” rather than a fabricated score.

### 10.6 Final assessment review and submission

**Heading:** “Ready to see your starting level?”

A compact checklist shows completed Grammar, Vocabulary, Writing, and either **Speaking submitted** or **Speaking skipped**.

**Primary CTA:** **Finish Assessment**.  
**Secondary:** Return to an editable step if allowed.

Submission confirmation should explain: “We'll review your responses and prepare your learning recommendations.” No need to ask the user to resubmit data already autosaved.

### 10.7 Processing state

**Heading:** “We're preparing your feedback.”

Progress labels may show **Reviewing your answers**, **Analyzing writing**, **Analyzing your recording** (only if present), and **Building your starting plan**. Use a non-numeric spinner or steps. Never claim a real-time percentage unless the backend can measure it reliably.

**Behavior:**

- Show friendly explainer and progress state.
- User may leave and return; the result is tied to their assessment, not the browser session.
- If processing is slow, show “You can come back later. Your answers are saved.”
- If temporary failure, show a retry/recovery message; don't erase submissions.
- If final evaluation fails, retain existing answers and offer retry/support.

### 10.8 CEFR result screen

**Heading:** “Here's a good place to begin.”

**Top result card:** “Your provisional English level: A2 — Elementary” (example only), confidence label, and “Why this is provisional” link.

**Skills panel:** Grammar, Vocabulary, Writing, Speaking; show **Not assessed** for skipped/unsupported skill instead of 0. If scores are included, label rubric scales clearly; never equate decorative progress-bar length with a certified CEFR scale.

**Strengths panel:** 2–3 specific observed strengths.  
**Growth opportunities:** 2–3 concrete improvement areas.

**Speaking feedback (if available):** Original recognized transcript, specific corrected examples, and a note that transcription may contain recognition errors. Do not present transcript-only scores as pronunciation analysis.

**Writing feedback:** Original writing, highlights/corrections, and optional improved example.

**Primary CTA:** **See My Learning Plan**.  
**Secondary:** **Review Assessment Feedback** (expand or scroll).

**Responsiveness:** Desktop two-column main score + highlights; mobile stacked cards with direct CTA.

### 10.9 Learning plan handoff screen

**Heading:** “Your first 21-day journey is ready.”

Summary: provisional placement, chosen goals, focus skills, selected daily time target, and one Day 1 preview per module.

Example cards:

- Speaking: **Introduce yourself at work** — about 6 minutes.
- Vocabulary: **10 words for work conversations** — about 4 minutes.
- Writing: **Write a short introduction** — about 5 minutes.

Add small explanation: “Your modules advance independently, so you can focus on one or all three.”

**Primary CTA:** **Go to My Dashboard**.  
**Optional upsell:** If a paid plan is selected as part of the approved business model, use a **non-blocking, clearly labeled plan upgrade card** below the first learning-plan summary; do not mask assessment results with a surprise payment gate.

---

## 11. Screen/state matrix and recovery behavior

| Situation | What the interface shows | Next action |
|---|---|---|
| New user first login | Goal selection | Choose goals |
| Preferences saved | Assessment introduction | Begin or return |
| Assessment partially answered | Current assigned item and saved state | Resume |
| Writing draft unfinished | Last saved draft and prompt | Continue writing |
| Microphone unavailable | Clear skip/retry card | Skip or retry |
| Speaking uploaded but not evaluated | Saved recording badge | Submit assessment / check status |
| Assessment processing | Honest processing state | Wait on screen or leave and return |
| Evaluation retrying | “Still processing your results” | Return later |
| Evaluation failed permanently | Recovery message, answers preserved | Retry where supported / contact help |
| Result ready | Provisional CEFR report | View plan |
| Plan initialization unavailable | Result preserved, helpful retry state | Retry safe plan initialization |
| Onboarding complete | Dashboard | Begin Day 1 |
| Checkout canceled | Subscription not activated | Retry or continue accessible learning |
| Payment pending | Verification pending | Refresh later; don't show paid unlock early |
| Payment completed | Confirmation based on verified backend status | Continue learning |

---

## 12. Responsive design guidance

| Viewport | Landing | Forms and assessment | Pricing |
|---|---|---|---|
| Large desktop | Wide sections, two-column hero | Centered single-task content | Two cards side-by-side |
| Tablet | Reduced columns, compact header | Comfortable centered column | Two cards or stacked depending width |
| Mobile | Single-column hero; visible CTA | Single-task cards; sticky navigation where useful | Stacked cards; full-width CTAs |

Additional requirements:

- Main CTAs and assessment controls should remain reachable without excessive scrolling.
- Recording buttons should have generous touch targets (aim for at least 44 × 44 CSS px).
- Don't hide word count, privacy explanations, or saved state on mobile.
- Respect reduced-motion preference; avoid mandatory animation when a result is announced.
- Ensure pricing period/terms are not truncated on narrow devices.

---

## 13. Accessibility and inclusive UX

- Aim for WCAG 2.2 AA in the core user journey.
- All questions and answers have semantic labels and visible keyboard focus.
- Never communicate selection, correctness, status, or errors by color alone.
- Announce saved-state changes and assessment transitions appropriately to assistive technology.
- Voice recording is optional; do not discriminate against learners who cannot use the microphone.
- Do not force rapid-response timers for users with different cognitive or accessibility needs.
- Caption explanatory videos; make decorative audio waveform nonessential.
- Text should remain usable with 200% zoom and with larger system font settings.
- Keep feedback empathetic and specific; avoid shaming wording or declaring someone “bad at English.”

---

## 14. Copywriting and content rules

### Brand voice

Warm, practical, encouraging. Celebrate effort without making unsupported claims.

| Location | Preferred copy | Avoid |
|---|---|---|
| Hero | “Practice English with a plan made for you.” | “Become fluent in 21 days.” |
| Assessment intro | “Find a good starting point.” | “Prove your English ability.” |
| Speaking skip | “Skip speaking for now.” | “Your assessment is invalid.” |
| Processing | “We're reviewing your answers.” | “99% accurate grading.” |
| Result | “Provisional starting level.” | “Official CEFR certification.” |
| Pricing | “See what's included in each plan.” | “Unlimited” unless truly contractually supported |
| Payment | “Review your total before paying.” | Hidden renewal terms or unverifiable guarantees |

### Content authenticity

Illustrative scores, testimonials, learner counts, plan prices, and product screenshots must be labeled **Example**, **Concept**, or replaced with verified production material. Do not fabricate learner ratings or partner logos.

---

## 15. Design component inventory (conceptual, not implementation)

**Shared marketing UI:** Logo/header, CTA button, benefit card, pillar card, “How It Works” stepper, preview screenshot frame, pricing plan card, billing cadence selector, comparison grid, pricing FAQ accordion, footer.

**Authentication UI:** Auth card, form field, password visibility control, Google login button, inline validation, notification/error banner.

**Onboarding UI:** Onboarding shell, selectable goal card, skill checkbox card, daily-minute selector, topic tag selector, comfort radio group, save indicator, continue/back navigation.

**Assessment UI:** Assessment shell, step indicator, question prompt card, single-choice answer group, plain-text writing editor, word counter, microphone permission card, audio recorder, playback card, review checklist, processing card, CEFR level card, skill evidence summary, correction list, plan preview.

**System UI:** Loading skeleton, empty state, offline notice, retry card, confirmation dialog for explicit destructive actions, toast for nonessential status, accessible inline error text.

---

## 16. Product analytics (design instrumentation requirements)

The UI should be designed to support an appropriately consented event funnel, without logging raw speaking audio, private writing, or unredacted assessment answers into marketing analytics.

| Step | Proposed product event | Purpose |
|---|---|---|
| Landing | `landing_viewed` | Reach |
| Main CTA | `get_started_clicked` | Signup interest |
| Pricing viewed | `pricing_viewed` | Monetization discovery |
| Plan selected | `plan_selected` | Plan preference |
| Checkout started | `checkout_started` | Purchase intent |
| Checkout verified | `checkout_verified` | Payment conversion, only after trusted confirmation |
| Registration | `signup_completed` | Account creation |
| Goals/preferences | `onboarding_preferences_completed` | Onboarding completion |
| Assessment intro | `assessment_started` | Assessment entry |
| Speaking | `speaking_skipped` / `speaking_submitted` | Recording completion/drop-off |
| Evaluation | `assessment_result_ready` | Result completion |
| Handoff | `learning_plan_opened` | Initial activation |

Track aggregate step drop-off and accessibility/technical failure rates, not personally sensitive language mistakes in third-party product analytics.

---

## 17. Final design acceptance criteria

### Landing and pricing

- [ ] Landing hero explains the three-pillar learning value in one glance.
- [ ] Primary CTA leads into signup and preserves navigation intent.
- [ ] Pricing appears clearly on the landing page.
- [ ] Pricing plans show **approved** prices, periods, limits, tax and renewal terms.
- [ ] Paid checkout uses a verified hosted payment flow when implemented.
- [ ] Payment success/pending/cancel/failure screens are unambiguous.
- [ ] No fabricated testimonials, outcomes, partners, or discounts.

### Authentication and onboarding

- [ ] Email and Google entry points are visible and accessible.
- [ ] Auth errors are clear and account existence isn't unnecessarily disclosed.
- [ ] Goals and preferences are saved and resumable.
- [ ] Multi-select goal/focus controls and validation are understandable.
- [ ] A returning learner resumes their saved step instead of starting over.

### Assessment

- [ ] Learners understand the estimated duration and what will be tested.
- [ ] Adaptive questions do not leak correct answers.
- [ ] Writing editor preserves the original learner response and indicates save status.
- [ ] Speaking recorder has permission, recording, preview, upload and skip states.
- [ ] Speaking can be skipped without inventing a pronunciation score.
- [ ] AI processing is represented honestly and can be resumed after navigation.
- [ ] Results clearly say **provisional CEFR** and identify unassessed skills.
- [ ] The learning-plan preview leads to the appropriate authenticated dashboard.
- [ ] Mobile, keyboard, screen reader and reduced-motion experiences are supported.

---

## 18. Open product decisions to resolve before final UI approval

1. **Billing model:** Free + Premium, premium-only, trial, one-time purchases, or subscriptions?
2. **Currency and regional support:** Which geographies and payment methods are supported?
3. **Commercial limits:** Exactly which practice and AI feedback functions differ by tier?
4. **Assessment access:** Is the initial assessment always free? (Recommended: yes.)
5. **Paid checkout timing:** Before onboarding, after results, or selectable from both positions?
6. **Billing policy:** Refunds, cancellation, renewal, invoicing, tax, support obligations.
7. **Email verification:** Required before onboarding or handled with a grace period?
8. **Assessment scoring:** Exact approved placement copy and minimum evidence for confident results.
9. **Marketing claims:** Are there verified screenshots, product reviews or usage numbers to display?
10. **Audio retention:** Final user-facing policy for recordings, transcription and deletion.

---

## 19. Suggested design handoff package

Before engineering implementation, the design team should produce:

1. A **page map** covering Landing, Auth, Onboarding, Assessment, Results, and Checkout states.
2. **Desktop and mobile wireframes** for every screen, including pricing cards and the recorder.
3. A **clickable prototype** of the main journey and the paid-plan branch.
4. **Component specifications** for buttons, form fields, cards, progress labels, pricing cards, and audio controls.
5. A **content inventory** with approved plan entitlements, prices, legal disclosures and privacy wording.
6. A **state matrix** for loading, saved, offline, permission denied, processing, failed, resume, pending payment and payment success.
7. An accessibility review and user testing plan for the assessment journey.

**Design completion definition:** A frontend engineer should be able to implement every screen and visible state without inventing business rules, payment terms, assessment outcomes, or missing-user behavior.

---

## 20. Relationship to existing TalkFiesta documents

This proposal is designed to be consistent with:

- `TalkFiesta.md` — original product definition and brand direction.
- `TalkFiesta-Simplified-Database-Schema-v4.md` — 14-model proposed learning-data architecture, without presuming billing is modeled.
- `TalkFiesta-Auth-to-Assessment-API-Flow-V4.md` — registration through first assessment and learning-plan creation.
- `TalkFiesta-AI-Assessment-API-Flow-V4.md` — asynchronous assessment processing and result retrieval.
- `TalkFiesta-Dashboard-and-Learning-Plan-APIs-V4.md` — first dashboard and next assigned daily activities.

**Important distinction:** The landing-page paid plan, checkout experience, and proposed free assessment policy are new design recommendations. They require product/business approval and a separate billing-domain design before implementation.
