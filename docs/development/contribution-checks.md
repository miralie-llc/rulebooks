# Contribution checks and pre-publication review

Use these checks before publishing a branch, pull request or preview. They implement [engineering issue #2](https://github.com/miralie-llc/rulebooks/issues/2) and the [repository policy](../product/repository-boundaries.md). A public CI run is already too late to prevent disclosure in the push that triggered it; local review comes first.

## Local checks

Use Python 3.11 and Git with complete local history:

```sh
python3 -m pip install -r tools/requirements-ci.txt
python3 tools/install_gitleaks.py
python3 tools/check_repository.py
python3 -m unittest discover -s tests -v
python3 tools/prepublish.py --candidate working --base origin/main
```

The scanner installer downloads Gitleaks 8.30.1 from its official release and verifies the archive against checked-in SHA-256 pins. It supports Linux/macOS on x64/arm64; the exercised CI platform is Linux x64. Downloads and the verified binary stay in ignored `.cache/tools/`. Every scan rechecks the archive and binary. No token is required and the scanner does not verify candidate credentials against external services. Review pin updates as tool changes. [Gitleaks documentation](https://github.com/gitleaks/gitleaks)

`--candidate working` checks tracked working files plus non-ignored new files. `--candidate index` checks exactly the staged blobs. `--candidate head` checks committed blobs, ignoring unstaged replacements. All modes also scan commits reachable from HEAD but not the explicitly named base. Refresh the intended destination's tracking ref before review; the script does not fetch or push. Use `--all-history` for an initial publication or when no base exists. This means all history reachable from HEAD, not unrelated branches or repositories. Shallow history and a base that is not an ancestor fail closed.

The local report at `.cache/review/prepublish.json` contains the candidate inventory/hash, HEAD and base, outgoing commit IDs, checker/scanner fingerprints and sanitized finding locations. It excludes credential values, matched source lines, author email and raw scanner output. Reports are private local working material, not committed artifacts. A failed attempt cannot leave a stale passing report at that destination.

Synthetic credential integration tests use disposable repositories and generated test strings. They never contact an account or use real credentials. These tests require the installed scanner; they skip locally if absent, while CI installs the scanner before running them.

## What is checked

| Check | Enforced behavior |
|---|---|
| Repository paths | Only maintained root files and source directories are eligible. Force-added private context, raw-reference directories, credentials, caches, archives and generated logs fail. Symlinks and submodules are rejected. The initial source allowlist is deliberately small; expanding it requires code review. |
| Markdown links | Check local paths and heading/HTML anchors in maintained Markdown, including reference links, images and tables. Ignore fenced/inline code examples. Do not fetch external citations or require private local context. |
| Work records | Validate schema, IDs, dependencies and evidence against an exported public candidate, so an ignored local file cannot satisfy evidence. |
| Promoted sources | Validate every `data/sources/<id>/<revision>.json` envelope, source/citation pins, review digest and public-locator restrictions without accessing private storage. |
| Draft knowledge contracts | Check synthetic chess, Nim and RPS draft/review projections and their artifact bindings. Reject top-level research draft/review/trace records outside marked knowledge fixtures. The unit suite checks evidence retention, inference dependencies, unresolved blockers and publication compatibility. Actual research stays outside Git. |
| Publication contracts | Check every persisted publication fixture in the exported candidate. The unit suite additionally tests exact references, attribution, coverage, hashes and history. Publication asset paths reject repository-only data, queues, tests, tools, private context and logs even if their hashes are valid. No actual site assembly is performed yet. |
| Credentials | Scan candidate file bytes, outgoing Git patches (including merges/root commits) and commit-message bodies. Detect additions later deleted from the branch. Use the pinned default rules, ignoring inline `gitleaks:allow` comments and repository ignore/config overrides. |
| Changed private paths in history | Reject forbidden paths even if later deleted. Legitimate old source layouts need not match today's source-directory allowlist. |

Rules and schemas cannot determine whether prose contains private business information, whether a source may be redistributed, or whether a rule mapping is true. Credential scans are detection aids, not a guarantee that all secrets or encodings are recognized. Investigate findings before publishing; do not add blanket exceptions to get a green result. If a real credential has already been published, revoke/rotate it and handle history cleanup separately.

## Human review and exact-candidate verification

Review the candidate diff, every outgoing commit and commit message, source permissions, personal/internal information and any embedded metadata. Keep that review outside public logs until the material is approved. A scanner result is not a human approval.

Treat changes to `.github/`, `tools/`, schemas, dependency/scanner pins and input policy as engineering changes, separately from content/source review. These files control what checks run. A content approval must not implicitly approve changes to the validation machinery. The PR template makes this distinction explicit; it does not substitute for configured reviewer enforcement.

After review and committing the intended changes, rerun the checks against the committed candidate and review that report:

```sh
python3 tools/prepublish.py --candidate head --base origin/main
```

Immediately before an authorized push, confirm the reviewed candidate/range/tooling still matches:

```sh
python3 tools/prepublish.py --candidate head --base origin/main --verify-report .cache/review/prepublish.json
```

This reruns the scans and compares the commit, range, file inventory and tool fingerprints. Publish only that reviewed commit to the intended destination; a different branch, tag or amended commit requires its own review. A matching report is not a signature, permission to publish, or evidence that the unit suite passed; run the suite for the same committed code and check its result as well.

There is no built site artifact yet. Issue #4 will assemble an explicit publication manifest and hashed output. At release time the maintainer must verify the artifact digest against the reviewed build's manifest and promote those exact bytes; source-level checks alone cannot approve a future build output. Test fixtures, work queues and the checkout as a whole must never be copied into the public site's release directory.

## CI and enforcement limits

[GitHub Actions](../../.github/workflows/validate.yml) installs pinned dependencies/scanner, fetches full history, scans the candidate and event's outgoing range, checks maintained links/work records and runs all contract/boundary tests. PRs use the base commit; pushes use the previous tip; manual/initial runs scan all reachable history. Missing/divergent bases fail instead of silently skipping history.

The workflow uses `pull_request`, a read-only contents token and checkout without persisted credentials. It uses no production secrets, privileged follow-up workflow, deployment environment or automatic publication. Raw scan reports are not uploaded as CI artifacts. [GitHub workflow security guidance](https://docs.github.com/en/actions/reference/security/secure-use)

Failing checks stop this workflow. Repository branch protection, mandatory reviewers and a local Git pre-push hook are **not configured by these files**. Local pre-publication review is a maintainer requirement, not an installed hook. Require the `Validate repository` status in repository rules before opening broad contributions; configure reviewer ownership when maintainers are designated. Protected deployment approvals belong to the later release setup. This keeps the current enforcement claims accurate while the product is built.
