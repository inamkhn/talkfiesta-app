# Assessment evaluation contracts

`app/modules/assessment/ai/schemas.py` defines internal Pydantic contracts. The
existing writing and speaking nodes now request these schemas. No migration or
new endpoint is needed.

## Provider output

`WritingEvaluation` and `SpeakingLanguageEvaluation` require every field:

- `sufficient_evidence`: a strict boolean.
- `cefr_level`: A1 through C2, or null when evidence is insufficient.
- `reason`: null for assessed responses, otherwise `INSUFFICIENT_EVIDENCE`.
- `criteria`: grammar, vocabulary, coherence, and task_completion. Each has a
  CEFR `level` and nonblank `feedback` of at most 600 characters.
- `strengths` and `improvement_priorities`: up to four nonblank strings, each
  at most 600 characters. Both lists must contain feedback when assessed.

With insufficient evidence, `cefr_level` and `criteria` must be null and both
feedback lists must be empty. Unknown fields and type coercion are rejected.
Writing remains required: insufficient writing evidence cannot produce a
successful placement. Optional speaking can be unassessed. Storage failures and
explicit skips are handled by the server, not invented by the language model.

Criterion levels are qualitative rubric judgments, not numerical scores or a
validated CEFR calibration. Overall placement remains the responsibility of the
existing versioned Python policy. The schema does not prove that an AI judgment
is correct or supported by the learner's answer.

Speaking evaluates transcript language only. Pronunciation, pace, and prosody
are not inferred. Public placement now explicitly includes:

```json
"pronunciation": {
  "level": null,
  "assessed": false,
  "reason": "AUDIO_PRONUNCIATION_NOT_EVALUATED"
}
```

This is an additive `skills` field; reading older results supplies this safe
default. An assessed pronunciation value is rejected.

## Final placement and execution

`PlacementResult` validates the graph output and is revalidated by the job runner
before the result transaction. It requires an overall CEFR, assessed grammar,
vocabulary and writing, bounded nonblank feedback, a nonblank rubric version,
and explicit speaking evidence status. Under `placement-policy-v2`, confidence
is LOW without assessed speaking and never HIGH for new results. Unexpected
fields are rejected, including in nested skill maps. See `assessment-placement-policy.md`.

The worker loads one claim-bound `AssessmentEvidence` snapshot. The evaluator
projects it into graph input without requerying the database. Objective answer
keys are not passed into graph input, and account identity is unnecessary there.
The job runner still checks its lease before saving.

The provider's criterion details are validated internally; the existing placement
policy consumes the skill level and summary feedback. The evaluator integration
now saves criterion feedback under each response's `grading.evaluation`, atomically
with the placement. Transcripts are temporarily checkpointed for retry reuse
(see `assessment-checkpoints.md`). The public response still
exposes only the placement projection.

Malformed or incomplete provider output uses the bounded job retry mechanism.
Explicit provider refusal and valid insufficient required writing evidence fail
without fabricated placement. No live provider,
S3, Redis, or PostgreSQL evaluation was performed for this change.
