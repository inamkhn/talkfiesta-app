# Worker evidence loading

`load_assessment_evidence(job_id, claim_token)` is implemented in
app/modules/assessment/ai/evidence.py and called by the gated worker before the
future evaluator. It is internal Python functionality, not an HTTP endpoint.

It requires a RUNNING ASSESSMENT job with an unexpired matching execution token,
an active owner, and that owner's PROCESSING initial assessment with submitted_at.
All reads happen in one read-only PostgreSQL REPEATABLE READ transaction. The
connection closes before any future transcription/evaluation call.

The loader checks the ten-item sequence, distinct assigned question IDs, saved
response revisions, finalized answer payloads, and pinned content release. It
recomputes objective correctness from private answer keys and rejects stored grade
mismatches. Writing must be finalized and nonblank. Question prompts are bounded
at 16,000 characters and rubric JSON at 64,000. Published and archived immutable
question rows are usable; draft/unpublished/missing content is rejected.

Returned frozen dataclasses contain:
- Assessment/job IDs, pinned release, submission timestamp.
- A tuple of question evidence with question/response IDs, revision, position,
  content version, kind, skill, CEFR band, prompt and relevant private rubric.
- Objective choices, learner choice, private correct choice and checked grade.
- Finalized writing text.
- A verified audio reference OR explicit speaking-unassessed reason.

Rubrics are immutable JSON strings, choices are tuples, and nested evidence is
frozen. Prompts, choices, answer keys, writing, audio keys/checksums, and the
question collection are excluded from default repr output. This does not make
arbitrary serialization safe: do not log asdict(), raw evidence or LangSmith
input payloads. No account email/name/profile or credentials are loaded into the
returned evidence, and it must never be used as an HTTP response model.

Audio references validate owner, response binding, purpose, verification status,
retention, canonical SHA-256, stored/expected size, allowed type, and duration.
Expired/deleted/unavailable optional audio becomes AUDIO_UNAVAILABLE; explicit
skips preserve their reason. Mismatched ownership/binding fails closed. This step
does not download S3 objects or prove they still exist: transcription must fetch
and recheck checksum/retention before use. No pronunciation is inferred.

The future evaluator signature is now:
`evaluate_assessment(evidence: AssessmentEvidence, report_stage: Callable)`.
This supersedes the earlier job-ID-only integration contract. It should not open
another transaction merely to reload these inputs. Stages/result writes remain
fenced by the runner because the claim can expire after evidence loading.

No data is copied into a new snapshot table. The implementation relies on the
existing freeze-on-submit rule and immutable published content. Administrative
database edits bypassing those rules are not detectable from the current schema.
Output contracts, OpenAI clients and evaluation logic remain separate next steps.

No migrations, provider calls, downloads or tests were added/run for this step.
