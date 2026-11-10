# Final assessment review and submission

When the backend detail response reports `can_submit`, `/level-assessment` renders the final review instead of another question. A new additive `sections` field on GET `/assessments/{id}` supplies per-skill totals, answered counts and skipped counts. No answer text, grading or answer keys are included. No database migration is required; deploy/restart the updated backend with the frontend.

The checklist displays completed grammar, vocabulary and writing, and either recorded or skipped speaking. It does not infer speaking completion from browser memory. Finalized answers cannot be edited.

Finish assessment explicitly calls POST `/assessments/{id}/submit` with an Idempotency-Key scoped to the user and attempt. The key is saved before the request and reused after uncertain failures. Pending requests disable duplicate actions. The existing backend transaction revalidates answers/audio, freezes the attempt and queues evaluation; the frontend never performs those mutations itself.

After a validated acceptance response, the UI refreshes server-owned onboarding state, updates route caches and opens processing, results or terminal failure as appropriate. It never navigates to an arbitrary result_url supplied in a response. If status loading fails after acceptance, the UI preserves the accepted state and retries status only. No second submission is needed.

409 conflicts expose the backend explanation and offer reloading the saved state. Rate limits and network failures preserve answers and allow safe retry. Save & exit before submission does not queue an evaluation. Returning after a lost response uses existing onboarding resume routing to discover the committed state.

Validation: TypeScript and targeted ESLint, Python compilation and Ruff, and whitespace checks. No automated tests added, real assessments submitted or evaluation jobs queued during implementation.

Real placement reports, result polling and learning-plan handoff are now connected; see assessment-results-handoff.md.
