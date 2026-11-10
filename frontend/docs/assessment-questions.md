# Live assessment questions and answer saves

`/level-assessment` now uses the real assessment APIs. `/design-preview` remains isolated sample content.

- An explicit Start action posts `{kind: INITIAL}` with an Idempotency-Key retained in sessionStorage across an uncertain retry. An existing attempt ID from onboarding state is resumed directly.
- GET assessment detail and current-item restore the saved question without creating a new question on page load. Continue assigns the next item through POST items/next. A 204 response is handled without attempting to parse JSON.
- Multiple-choice options come from the backend; no correctness or placement feedback is exposed during the assessment.
- All answer writes carry the assigned response ID and expected revision. Buttons are locked during saves. Finalized answers stay locked even if loading the next item fails.
- Writing supports explicit Save draft, Save draft & exit, and Finalize writing & continue. No automatic rewriting or autosave occurs. Unsaved changes are indicated and browser unload warns before losing them.
- The backend public item contract now includes optional `draft_text`, limited to the learner's own assigned writing response. This additive field restores drafts across reloads/devices; rubrics, grading and answer keys remain excluded. No migration is needed.
- Revision conflicts preserve the local text and require explicit discard/reload before another save. Network failures permit retry; the backend recognizes an immediately repeated identical write.
- Speaking now supports microphone recording, playback, re-recording, signed upload, confirmation and revision-aware save. Optional skip remains available; see assessment-audio.md.
- When all required items are answered, the server's can_submit flag shows that answers are saved. Final review and submission are now connected. Result reports and learning-plan handoff are now connected.

Validation: TypeScript and targeted ESLint; Python compilation and Ruff for the two backend files. No tests added, live accounts modified, or AI jobs queued.
