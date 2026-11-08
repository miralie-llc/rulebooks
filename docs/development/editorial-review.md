# Editorial submissions and change review

Content and semantic work remain canonical in `work/`, using [the existing schema](../../schema/work-item.schema.json). The [content](../../.github/PULL_REQUEST_TEMPLATE/content.md) and [semantic-gap](../../.github/PULL_REQUEST_TEMPLATE/semantic-gap.md) pull-request templates collect the review context without creating a second issue-based product database. An upstream team's genuine review may accompany publication records directly; private intake is optional.

A contributor supplies exact changed identities, scope, citations/editorial origin, evidence, acceptance criteria and the existing work record. A semantic item needs an actual rule or demonstrated limitation, not a hypothetical need for a new primitive. Draft records and candidate source remain visibly pending until accepted.

## Generate a local review

```sh
python3 tools/editorial_diff.py --base origin/main
npm run build
npm run preview
```

The diff runs credential/structural pre-publication checks first, compares the exact Git base to the working candidate, and records its snapshot digest. Reports stay under ignored `.cache/review/` with restricted local permissions. No acceptance or public deployment occurs. Re-run after any edit; an old report does not approve new bytes.

Rule diffs retain stable rule IDs, before/after statements and origins, metadata changes and record digests. Formalization diffs include rule coverage rows. Definition diffs execute both sources through the current reference implementation and compare reachable outcomes, observations, legal intents, probabilities and resulting states. They record implementation identity and explicit exploration limits; exceeding 128 states or 4,096 transitions makes the comparison incomplete. An invalid/unsupported source is reported, never treated as equivalent. This comparison does not claim to reproduce a previous runtime build.

Use the existing site build as the publication-safe preview: its inputs, projections and download inventory have their own checks. Keep private notes and captures outside Git and PR descriptions. Attach only the public review context needed for accountable acceptance. The publication contract records the genuine responsible reviewer, exact reviewed digest and accepted commit; tools do not manufacture these from test results.

## Remaining evolution gate

Submission templates, exact candidate identification and measured diffs are implemented. Issue #11 remains open: a real accepted version-evolution cycle still needs initial acceptance, and withdrawal packaging still deliberately fails closed. Retaining a removed payload inside an old bundle would silently republish it. Removal policy, historical download/tombstone treatment and release verification must be implemented together before enabling withdrawals. These limits do not prevent preparing or reviewing ordinary additive revisions.

The Nim candidate is pending editorial review. No artificial second revision, accepted review or hypothetical semantic task is created merely to satisfy an evolution demonstration.
