"""Exercise publication boundaries with isolated, disposable Git repositories."""

import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from tools.check_repository import (
    CheckError, ROOT, check_links, inventory, snapshot, validate_candidate,
)
from tools.input_policy import publication_path_problem, repository_path_problem
from tools.install_gitleaks import scanner_path, verified_binary
from tools.prepublish import check_history_paths, outgoing_commits, prepublish, same_review
from tools.validate_publication import ContractError, load_json, validate_bundle
from test_publication import FIXTURES, get, seal


def run_git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    return result.stdout.decode().strip()


class TemporaryRepo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rulebooks-contribution-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        run_git(self.root, "init", "-b", "main")
        run_git(self.root, "config", "user.name", "Fixture author")
        run_git(self.root, "config", "user.email", "fixture@example.invalid")
        self.write(".gitignore", ".env\nreference/\n.private/\n.cache/\nLOCAL_CONTEXT.md\n")
        self.write("README.md", "# Fixture\n\n[Work](work/content/content-fixture.json)\n")
        self.write("schema/work-item.schema.json", (ROOT/"schema/work-item.schema.json").read_text())
        self.write("work/content/content-fixture.json", json.dumps({
            "schemaVersion":"0.1.0", "id":"content-fixture", "queue":"content", "kind":"wishlist",
            "title":"Test only", "status":"proposed", "target":{"kind":"candidate-game","id":"fixture"},
            "acceptance":["Contract test only"],
        }))
        self.base = self.commit("Initial fixture")

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self, message):
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-m", message)
        return run_git(self.root, "rev-parse", "HEAD")


class InputBoundaryTests(TemporaryRepo):
    def test_private_ignored_files_never_enter_candidate(self):
        for name in [".env", "reference/raw.txt", ".private/notes.md", "LOCAL_CONTEXT.md"]:
            self.write(name, "private test content")
        files = snapshot(self.root)
        self.assertEqual(len(files), 4)
        self.assertEqual(validate_candidate(files)["workRecords"], 1)

    def test_force_added_private_file_rejected_before_reading(self):
        self.write(".env", "private test content")
        run_git(self.root, "add", "-f", ".env")
        with self.assertRaisesRegex(CheckError, "Rejected repository path"):
            snapshot(self.root, "index")

    def test_private_file_removed_from_tip_still_rejected_in_history(self):
        self.write("reference/capture.txt", "private fixture")
        run_git(self.root, "add", "-f", "reference/capture.txt")
        self.commit("Add private capture fixture")
        (self.root/"reference/capture.txt").unlink()
        head = self.commit("Remove capture")
        commits, _ = outgoing_commits(self.root, head, self.base)
        with self.assertRaisesRegex(CheckError, "Outgoing history contains rejected path"):
            check_history_paths(self.root, commits)

    def test_index_and_head_use_blobs_not_unstaged_bytes(self):
        expected = (self.root/"README.md").read_bytes()
        self.write("README.md", "unstaged replacement")
        self.assertEqual(snapshot(self.root, "index")["README.md"], expected)
        self.assertEqual(snapshot(self.root, "head")["README.md"], expected)
        self.assertNotEqual(snapshot(self.root)["README.md"], expected)

    def test_untracked_source_is_checked_but_untracked_capture_is_rejected(self):
        self.write("docs/new.md", "# New\n")
        self.assertIn("docs/new.md", snapshot(self.root))
        self.write("docs/capture.pdf", "raw source placeholder")
        with self.assertRaisesRegex(CheckError, "allowlist"):
            snapshot(self.root)

    def test_symlink_never_reads_private_target(self):
        (self.root/"docs").mkdir()
        (self.root/"docs/link.md").symlink_to(self.root/".env")
        self.write(".env", "private fixture")
        with self.assertRaisesRegex(CheckError, "Symlinks"):
            snapshot(self.root)

    def test_queue_evidence_cannot_depend_on_ignored_local_files(self):
        self.write("reference/private.md", "Exists locally, absent from public candidate")
        record = json.loads((self.root/"work/content/content-fixture.json").read_text())
        record["evidence"] = [{"path":"reference/private.md", "note":"Must fail"}]
        self.write("work/content/content-fixture.json", json.dumps(record))
        with self.assertRaisesRegex(ValueError, "Evidence must name an existing repository file"):
            validate_candidate(snapshot(self.root))

    def test_repository_and_publication_have_distinct_allowlists(self):
        for name in [".env", "sources/.env", "reference/raw.txt", ".private/draft.md", "sources/key.pem", "logs/build.txt", "archive/old.json"]:
            with self.subTest(name=name):
                self.assertIsNotNone(repository_path_problem(name))
                self.assertIsNotNone(publication_path_problem(name))
        for name in ["tests/fixtures/test.json", "work/content/content-fixture.json", "tools/check.py", "docs/guide.md"]:
            self.assertIsNone(repository_path_problem(name))
            self.assertIsNotNone(publication_path_problem(name))
        self.assertIsNone(publication_path_problem("sources/game.gdl"))

    def test_publication_validator_rejects_private_assets_even_with_valid_hashes(self):
        bundle = load_json(FIXTURES/"first-games.json")
        file = get(bundle, "DefinitionPackage")["files"][0]
        old_path = file["path"]
        file["path"] = "reference/capture.txt"
        for export in get(bundle, "DefinitionPackage")["exports"]:
            if export["file"] == old_path:
                export["file"] = file["path"]
        seal(bundle)
        with self.assertRaisesRegex(ContractError, "Disallowed publication asset"):
            validate_bundle(bundle, FIXTURES, allow_fixtures=True)

    def test_inventory_changes_with_bytes_and_paths(self):
        first = inventory({"docs/a.md":b"one"})
        self.assertNotEqual(first, inventory({"docs/a.md":b"two"}))
        self.assertNotEqual(first, inventory({"docs/b.md":b"one"}))
        self.assertEqual(inventory({"b":b"b", "a":b"a"}), inventory({"a":b"a", "b":b"b"}))


class DocumentationTests(unittest.TestCase):
    def test_links_images_references_tables_and_anchors(self):
        files = {
            "README.md":b'# Start\n[inline](docs/a.md#same-1)\n![image](docs/image.txt)\n[reference][r]\n\n[r]: docs/a.md#named\n\n|A|\n|-|\n|[table](docs/a.md)|\n',
            "docs/a.md":b'# Same\n## Same\n<a id="named"></a>\n[back](../README.md#start)\n',
            "docs/image.txt":b'fixture',
        }
        self.assertEqual(check_links(files), 5)

    def test_code_examples_are_not_links_and_external_links_are_not_fetched(self):
        self.assertEqual(check_links({"README.md":b'`[example](absent.md)`\n\n```md\n[example](also-absent.md)\n```\n[external](https://example.invalid/no-fetch)\n'}), 0)

    def test_missing_path_anchor_and_escaping_link_fail(self):
        for href in ["missing.md", "#missing", "../private.md", "docs/a.md#absent"]:
            with self.subTest(href=href), self.assertRaises(CheckError):
                check_links({"README.md":f"# Main\n[bad]({href})".encode(), "docs/a.md":b"# Existing"})

    def test_html_links_and_identifiers_are_checked(self):
        self.assertEqual(check_links({"README.md":b'<a id="target"></a><a href="#target">Jump</a>'}), 1)
        with self.assertRaises(CheckError):
            check_links({"README.md":b'<a href="file:///private/note">Bad</a>'})


class ScannerIntegrityTests(unittest.TestCase):
    def test_archive_digest_verified_before_extracting_binary(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo("gitleaks")
            payload = b"test binary bytes, never executable"
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        data = stream.getvalue()
        self.assertEqual(verified_binary(data, hashlib.sha256(data).hexdigest()), payload)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            verified_binary(data, "0"*64)


class CredentialScanTests(TemporaryRepo):
    @classmethod
    def setUpClass(cls):
        try:
            cls.binary, cls.identity = scanner_path()
        except ValueError:
            raise unittest.SkipTest("Install the pinned scanner to run credential integration tests (required in CI)")

    def token(self):
        # A synthetic scanner trigger, assembled only inside a disposable test repo.
        return "gh" + "p_" + hashlib.sha256(b"not-a-real-token").hexdigest()[:36]

    def check(self, candidate="head", base=None):
        return prepublish(self.root, candidate=candidate, base=base or self.base,
                          binary=self.binary, tool_identity=self.identity)

    def test_clean_candidate_report_and_stale_review_detection(self):
        report = self.check()
        self.assertEqual(report["status"], "passed")
        same_review(report, self.check())
        self.write("README.md", "# Changed\n")
        with self.assertRaisesRegex(CheckError, "differs"):
            same_review(report, self.check("working"))

    def test_secret_in_uncommitted_candidate_is_redacted(self):
        self.write("docs/note.md", 'token = "' + self.token() + '"\n')
        report = self.check("working")
        self.assertEqual(report["status"], "failed")
        self.assertNotIn(self.token(), json.dumps(report))
        self.assertNotIn("Secret", json.dumps(report))

    def test_deleted_secret_remains_detectable_in_outgoing_history(self):
        self.write("docs/note.md", 'token = "' + self.token() + '"\n')
        leaked = self.commit("Add synthetic scanner fixture")
        (self.root/"docs/note.md").unlink()
        self.commit("Delete fixture")
        report = self.check()
        self.assertEqual(report["status"], "failed")
        self.assertIn(leaked, {f["commit"] for f in report["findings"]})
        self.assertNotIn(self.token(), json.dumps(report))

    def test_commit_message_is_scanned_without_echoing_it(self):
        self.write("docs/note.md", "ordinary content")
        self.commit("Synthetic message token = " + self.token())
        report = self.check()
        self.assertEqual(report["status"], "failed")
        self.assertNotIn(self.token(), json.dumps(report))

    def test_inline_suppression_cannot_hide_a_secret(self):
        self.write("docs/note.md", 'token = "' + self.token() + '" # gitleaks:allow\n')
        report = self.check("working")
        self.assertEqual(report["status"], "failed")

    def test_unknown_base_and_nonancestor_base_fail_closed(self):
        with self.assertRaises(CheckError):
            self.check(base="does-not-exist")
        self.write("docs/a.md", "one")
        later = self.commit("Second")
        with self.assertRaisesRegex(CheckError, "ancestor"):
            outgoing_commits(self.root, self.base, later)


if __name__ == "__main__":
    unittest.main()
