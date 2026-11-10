# Provisional placement policy review

Implemented policy version: `placement-policy-v2`.

The V4 documents require deterministic, versioned, provisional placement and
reduced confidence when speaking is unavailable. They do not define statistical
calibration, exact weights, or confidence thresholds. These are conservative
product heuristics, not scientifically calibrated CEFR cutoffs. Expert review
and validation against representative learner data are still required.

## Changes from the previous implementation

- Require exactly four valid grammar and four valid vocabulary outcomes, matching
  the shared assignment blueprint. Reject invalid CEFR values and non-boolean grades.
- Keep the existing adaptive-path estimate, but never assign an objective band
  above the highest band answered correctly. Previously the estimate could round
  up into an unproven band.
- Replace float arithmetic/Python tie-to-even rounding with exact integer weights
  and nearest-band rounding that always chooses the lower band at an exact tie.
- Validate productive-skill evidence without repairing contradictions. Unassessed
  skills require a reason, no level, and no scored feedback; writing is required.
- Remove HIGH confidence from new worker results. The public reader still accepts
  historical HIGH results, so this does not rewrite existing placements.
- Describe objective strengths using actual correct counts rather than claiming
  mastery of a CEFR band from four answers.

## Objective skill estimate

Map A1 through C2 to indices 0 through 5. The existing path rule estimates one
band above a correct item's band or one below an incorrect item's band, bounded
to 0–5. Take the midpoint of the final path estimate and the highest correctly
answered band, round to the nearest band with downward ties, and cap at that
highest correctly answered band.

If no question in a skill was answered correctly, A1 is the supported learning
plan floor, not evidence that A1 proficiency was demonstrated. Overall confidence
is LOW in this case. There is no pre-A1 level in the current product contract.

## Overall placement

Existing weights are preserved:

| Evidence available | Grammar | Vocabulary | Writing | Speaking |
|---|---:|---:|---:|---:|
| All four skills | 20% | 20% | 30% | 30% |
| Speaking unassessed | 30% | 30% | 40% | Excluded |

Compute the weighted band index and round to the nearest band, with exact
halfway ties going to the lower band. CEFR bands are ordinal; treating them as
equally spaced for this average is a product heuristic, not a psychometric model.
No pronunciation grade contributes to placement.

## Confidence

- MEDIUM only when speaking is assessed, all four skill bands lie within one
  band of each other, and each objective skill has at least one correct answer.
- LOW when speaking is unassessed, skill spread exceeds one band, or either
  objective skill has no correct answer.
- Never HIGH for this short, uncalibrated blueprint.

For example, A2 grammar plus B1 vocabulary/writing/speaking gives a provisional
B1 placement with MEDIUM confidence (assuming positive objective evidence).
With the same first three skill bands and speaking skipped, placement remains
B1 but confidence becomes LOW. A weighted index of 2.5 selects B1, not B2.

Confidence is a qualitative product label, not a probability or confidence interval.

## Versioning and scope

New saved `assessment_attempts.result` objects include the internal `policy_version`.
The language `rubric_version` is separate and unchanged. Existing results are not
recomputed. Checkpoints cache language/transcription evidence, not placement, so
recovered jobs recompute placement under the current policy without needing a new
provider call when the evidence checkpoint remains valid.

The public response/progress endpoint is not expanded in this step. No migration,
deployment changes, tests, or live integration runs are included. Local lint,
imports, schema generation, and graph compilation provide structural checks only;
they do not establish scoring accuracy or calibration.
