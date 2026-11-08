"""Scan candidate files and outgoing history; write only sanitized review metadata."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

if __package__:
    from .check_repository import CheckError, ROOT, commit_id, export_files, git, inventory, snapshot, validate_candidate
    from .install_gitleaks import scanner_path
    from .input_policy import common_problem
else:
    from check_repository import CheckError, ROOT, commit_id, export_files, git, inventory, snapshot, validate_candidate
    from install_gitleaks import scanner_path
    from input_policy import common_problem


def outgoing_commits(root, head, base=None):
    if git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise CheckError("Full local history is required; fetch it before scanning")
    if base:
        process = subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=root, capture_output=True)
        if process.returncode:
            raise CheckError("Base must be an ancestor of the candidate head")
    revision_range = f"{base}..{head}" if base else head
    return git(root, "rev-list", "--reverse", revision_range).decode().split(), revision_range


def check_history_paths(root, commits):
    for commit in commits:
        for name in filter(None, git(root, "ls-tree", "-rz", "--name-only", commit).decode().split("\0")):
            # Retired source layouts can be legitimate history; private paths cannot.
            problem = common_problem(name)
            if problem:
                raise CheckError(f"Outgoing history contains rejected path ({problem}) at {commit[:12]}: {name}")


def scan(binary, mode, target, directory, *, log_options=None):
    report = directory / (mode + ".json")
    config = directory / "scanner.toml"
    config.write_text('[extend]\nuseDefault = true\n')
    ignore = directory / "empty-ignore"
    ignore.write_text("")
    command = [str(binary), mode, str(target), "--config", str(config),
               "--gitleaks-ignore-path", str(ignore), "--ignore-gitleaks-allow",
               "--redact=100", "--no-banner", "--no-color", "--max-decode-depth=5",
               "--report-format=json", "--report-path", str(report), "--timeout=120"]
    if log_options:
        command.append("--log-opts=" + log_options)
    # No user token/config environment or external diff helpers enter the scanner.
    env = {"PATH":os.defpath, "HOME":str(directory), "GIT_CONFIG_NOSYSTEM":"1", "GIT_CONFIG_GLOBAL":os.devnull}
    process = subprocess.run(command, cwd=directory, env=env, capture_output=True, timeout=150)
    if process.returncode not in {0, 1} or not report.is_file():
        raise CheckError("Credential scanner failed; no passing review report was produced")
    findings = json.loads(report.read_text())
    if not isinstance(findings, list) or process.returncode == 1 and not findings:
        raise CheckError("Credential scanner returned an inconsistent result")
    # Never persist Match, Secret, line content, author emails, or raw process output.
    return [{"rule":item["RuleID"], "file":item["File"], "line":item["StartLine"],
             "commit":item.get("Commit", "")} for item in findings]


def prepublish(root, *, candidate, head="HEAD", base=None, binary=None, tool_identity=None):
    root = Path(root).resolve()
    head = commit_id(root, head)
    base = commit_id(root, base) if base else None
    commits, revision_range = outgoing_commits(root, head, base)
    check_history_paths(root, commits)
    files = snapshot(root, candidate, head)
    if binary is None:
        binary, tool_identity = scanner_path()
    with tempfile.TemporaryDirectory(prefix="rulebooks-secret-check-") as temp:
        directory = Path(temp)
        candidate_dir = directory / "candidate"
        candidate_dir.mkdir()
        export_files(files, candidate_dir)
        # Git patch scans may omit commit-message bodies; scan them as text too.
        messages = directory / "messages"
        messages.mkdir()
        for commit in commits:
            (messages / (commit + ".txt")).write_bytes(git(root, "show", "-s", "--format=%B", commit))
        findings = scan(binary, "dir", candidate_dir, directory)
        if commits:
            options = revision_range + " --full-history --root -m --no-ext-diff --no-textconv"
            findings += scan(binary, "git", root, directory, log_options=options)
            findings += scan(binary, "dir", messages, directory)
    # Structural checks run only after credential scans, reducing accidental log disclosure.
    checks = validate_candidate(files) if not findings else None
    checker = inventory({path.relative_to(ROOT).as_posix():path.read_bytes() for path in (ROOT / "tools").rglob('*')
                         if path.is_file() and path.suffix in {".py", ".json", ".txt"}})
    return {"reportVersion":"0.1.0", "candidate":candidate, "head":head, "base":base,
            "outgoingCommits":commits, "snapshot":inventory(files), "scanner":tool_identity,
            "checker":checker,
            "status":"failed" if findings else "passed", "findings":findings, "checks":checks,
            "humanConfidentialityReview":"required; not performed by this tool"}


def same_review(prior, current):
    fields = ["reportVersion", "candidate", "head", "base", "outgoingCommits", "snapshot", "scanner", "checker", "status", "checks"]
    if prior.get("status") != "passed" or current["status"] != "passed" or any(prior.get(k) != current[k] for k in fields):
        raise CheckError("Candidate/range/tooling differs from the passing review report; review again")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=["working", "index", "head"], default="working")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--base", help="Locally fetched destination tip; never fetched by this tool")
    selection.add_argument("--all-history", action="store_true", help="Scan every commit reachable from HEAD")
    parser.add_argument("--report", type=Path, default=ROOT / ".cache/review/prepublish.json")
    parser.add_argument("--verify-report", type=Path, help="Recheck exact bytes/range against an earlier passing report")
    args = parser.parse_args()
    # Reports remain private local output; never let a report overwrite authored inputs.
    report = args.report.resolve()
    if not report.is_relative_to((ROOT / ".cache/review").resolve()):
        parser.error("Reports must stay under .cache/review/")
    try:
        result = prepublish(ROOT, candidate=args.candidate, base=args.base)
        if args.verify_report:
            same_review(json.loads(args.verify_report.read_text()), result)
        report.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        report.write_text(json.dumps(result, indent=2) + "\n")
        report.chmod(0o600)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        # Never leave a stale success report after a failed attempt.
        report.unlink(missing_ok=True)
        parser.exit(1, f"Pre-publication check failed: {error}\n")
    if result["status"] != "passed":
        parser.exit(1, f"Credential findings: {len(result['findings'])}; inspect the sanitized local report.\n")
    print(f"Checked {len(result['snapshot']['files'])} candidate files and {len(result['outgoingCommits'])} outgoing commits.")
    print(f"Candidate SHA-256: {result['snapshot']['sha256']}")
    print("Credential and structural checks passed. Human confidentiality review is still required.")


if __name__ == "__main__":
    main()
