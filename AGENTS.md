# Working on RuleBooks

- Start with `docs/product/README.md` and the relevant current product document. These are the selected direction; BGSM belongs to RuleBooks.
- If an optional, Git-ignored `LOCAL_CONTEXT.md` exists, read its referenced index for orientation when accessible. Missing context is normal and must not block work. Read individual historical notes only when relevant; personal context never overrides the maintained project or supplies required build/test inputs.
- `work/` contains the canonical product content and semantic queues. Software implementation tickets are separate. Validate queue changes with `python3 tools/validate_work.py`.
- Publisher editions identify different game versions; RuleBooks revisions identify our records. Never use a record revision as a publisher edition number. Follow `docs/product/data-and-versioning.md`.
- Treat the checkout as intended for public release. Keep credentials, private correspondence, raw source captures and agent transcripts out of authored files. Do not read unrelated local credential stores or neighboring private projects for ordinary product work.
- Follow `docs/product/repository-boundaries.md` for public publication and private reference storage. An ignored file is not access-controlled. Do not push, open a public PR, or publish a preview without authorization for that action.
- Security/publication review must include all candidate files and outgoing history. Ignore rules are an accidental-add guard, not a security boundary.
