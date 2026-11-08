"""Contract integrity tests, not game conformance or editorial approval."""

import copy
import tempfile
import unittest
from pathlib import Path

from tools.validate_publication import (
    ContractError, digest, load_json, manifest_entry, reviewed_digest, validate_bundle,
)

FIXTURES = Path(__file__).parent / "fixtures/publication"


def seal(bundle):
    """Re-sign fictional test reviews so mutations exercise relational validation."""
    for record in bundle["records"]:
        if "review" in record:
            record["review"]["reviewedDigest"] = reviewed_digest(record)
    bundle["publication"]["manifest"] = [manifest_entry(r) for r in bundle["records"]]
    bundle["publication"]["review"]["reviewedDigest"] = reviewed_digest(bundle["publication"])
    return bundle


def get(bundle, kind, id=None, revision=None):
    return next(r for r in bundle["records"] if r["kind"] == kind and (id is None or r.get("id") == id) and (revision is None or r.get("revision") == revision))


class PublicationContractTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load_json(FIXTURES / "first-games.json")

    def validate(self, bundle=None, **kw):
        return validate_bundle(self.bundle if bundle is None else bundle, FIXTURES, allow_fixtures=True, **kw)

    def invalid(self, message, bundle=None):
        bundle = self.bundle if bundle is None else bundle
        seal(bundle)
        with self.assertRaisesRegex(ContractError, message):
            self.validate(bundle)

    def test_three_games_distinguish_reading_coverage_and_execution(self):
        result = self.validate()
        self.assertEqual(result["games"], 3)
        self.assertEqual(result["formalCoverage"], {
            "Formalization/fixture-nim-mapping/1":"complete",
            "Formalization/fixture-rps-mapping/1":"partial",
        })
        chess = get(self.bundle, "RulebookEdition", "chess-fide-mechanics")
        self.assertEqual(chess["readingStatus"], "partial")
        self.assertFalse(any(r["kind"] in {"BuildArtifact", "VerificationRecord"} for r in self.bundle["records"]))
        self.assertFalse(any(r["kind"] == "Formalization" and r["edition"]["id"] == chess["id"] for r in self.bundle["records"]))
        self.assertFalse(any(r["kind"] == "PublisherEdition" for r in self.bundle["records"]))

    def test_publisher_editions_are_distinct_games_and_prose_revision_is_not(self):
        bundle = load_json(FIXTURES / "publisher-editions.json")
        self.assertEqual(self.validate(bundle)["games"], 2)
        revisions = [r for r in bundle["records"] if r["kind"] == "RulebookEdition" and r["gameId"] == "fixture-orchard-1"]
        self.assertEqual([r["revision"] for r in revisions], [1, 2])
        self.assertEqual(revisions[0]["sections"], revisions[1]["sections"])

    def test_fixture_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ContractError, "explicit --allow-fixtures"):
            validate_bundle(self.bundle, FIXTURES)

    def test_relabeling_fixture_as_publication_is_rejected(self):
        self.bundle["purpose"] = "publication"
        self.invalid("Fixture marker mismatch")

    def test_minimal_publication_shape_without_formalization(self):
        # Synthetic positive path: structural acceptance does not authenticate review.
        bundle = load_json(FIXTURES / "publisher-editions.json")
        bundle["purpose"] = "publication"
        bundle["publication"]["commit"] = "1" * 40
        for record in bundle["records"]:
            del record["testOnly"]
        seal(bundle)
        self.assertEqual(validate_bundle(bundle, FIXTURES)["formalCoverage"], {})

    def test_unknown_fields_rejected(self):
        get(self.bundle, "Game")["privateNotes"] = "No hidden fields in public records."
        self.invalid("Schema error")

    def test_exact_versions_and_integer_revisions_required(self):
        for value in ["latest", "^0.1.0", "0.1", ">=0.1.0", "*"]:
            with self.subTest(value=value):
                bundle = copy.deepcopy(self.bundle)
                get(bundle, "Formalization")["language"]["version"] = value
                self.invalid("Schema error", bundle)
        get(self.bundle, "Game")["defaultEdition"]["revision"] = "latest"
        self.invalid("Schema error")

    def test_dangling_pin_rejected_even_if_it_looks_exact(self):
        get(self.bundle, "Formalization")["bgsm"] = "9.0.0"
        self.invalid("Dangling BGSMRelease")

    def test_duplicate_record_pin(self):
        self.bundle["records"].append(copy.deepcopy(self.bundle["records"][0]))
        self.bundle["records"][-1]["title"] = "Conflicting title"
        self.invalid("Duplicate record pin")

    def test_default_edition_cannot_cross_games(self):
        get(self.bundle, "Game", "chess")["defaultEdition"] = {"id":"nim-one-two", "revision":1}
        self.invalid("Default edition belongs to another game")

    def test_publisher_identity_cannot_move_to_another_game(self):
        bundle = load_json(FIXTURES / "publisher-editions.json")
        get(bundle, "Game", "fixture-orchard-2")["publisherEdition"] = {"id":"fixture-orchard-1-publisher", "revision":1}
        self.invalid("Publisher edition belongs to another game", bundle)

    def test_one_game_cannot_gain_second_publisher_identity(self):
        bundle = load_json(FIXTURES / "publisher-editions.json")
        extra = copy.deepcopy(get(bundle, "PublisherEdition"))
        extra["id"] = "unexpected-publisher-edition"
        bundle["records"].append(extra)
        self.invalid("identity links disagree", bundle)

    def test_content_lineage_cannot_move_games(self):
        bundle = load_json(FIXTURES / "publisher-editions.json")
        get(bundle, "RulebookEdition", "fixture-orchard-1-standard", 2)["gameId"] = "fixture-orchard-2"
        self.invalid("another game|lineage cannot change", bundle)

    def test_rule_ids_unique_across_sections(self):
        edition = get(self.bundle, "RulebookEdition", "nim-one-two")
        edition["sections"][1]["rules"][0]["id"] = "players"
        self.invalid("Duplicate rule ID")

    def test_readable_rules_require_effective_attribution(self):
        del get(self.bundle, "RulebookEdition", "nim-one-two")["origin"]
        self.invalid("Every rule needs an origin")

    def test_rule_citation_must_resolve(self):
        edition = get(self.bundle, "RulebookEdition", "chess-fide-mechanics")
        edition["sections"][0]["rules"][0]["origin"]["citations"][0]["source"]["revision"] = 2
        self.invalid("Dangling Source")

    def test_coverage_cannot_silently_omit_or_duplicate_rules(self):
        mapping = get(self.bundle, "Formalization")
        mapping["coverage"].pop()
        self.invalid("every edition rule")
        mapping["coverage"].append(copy.deepcopy(mapping["coverage"][0]) | {"reason":"duplicate"})
        self.invalid("Duplicate coverage row")

    def test_represented_rule_needs_definition(self):
        del get(self.bundle, "Formalization")["coverage"][0]["definitions"]
        self.invalid("Schema error")

    def test_coverage_definition_must_be_exported(self):
        get(self.bundle, "Formalization")["coverage"][0]["definitions"][0]["definition"] = "missing"
        self.invalid("Dangling exported definition")

    def test_coverage_cannot_borrow_unrelated_package(self):
        get(self.bundle, "Formalization")["coverage"][0]["definitions"][0] = {"package":{"id":"fixture-rps", "revision":1}, "definition":"tie"}
        self.invalid("outside package dependency closure")

    def test_outside_scope_is_visible_and_never_hides_in_denominator(self):
        mapping = get(self.bundle, "Formalization")
        mapping["coverage"][0] = {"rule":"players", "status":"outside-declared-scope", "reason":"Players not modeled"}
        self.invalid("must be declared")
        mapping["scope"]["excludes"].append("Players not modeled")
        seal(self.bundle)
        self.assertEqual(self.validate()["formalCoverage"]["Formalization/fixture-nim-mapping/1"], "partial")

    def test_unrepresented_row_needs_reason(self):
        del get(self.bundle, "Formalization", "fixture-rps-mapping")["coverage"][0]["reason"]
        self.invalid("Schema error")

    def test_partial_row_requires_both_mapping_and_reason(self):
        row = get(self.bundle, "Formalization")["coverage"][0]
        row["status"] = "partial"
        self.invalid("Schema error")
        row["reason"] = "Fixture maps only some player information."
        seal(self.bundle)
        self.assertEqual(self.validate()["formalCoverage"]["Formalization/fixture-nim-mapping/1"], "partial")

    def test_language_mismatch_rejected(self):
        get(self.bundle, "Formalization")["language"]["version"] = "0.0.0-fixture.2"
        self.invalid("language mismatch")

    def test_package_cycles_rejected(self):
        package = get(self.bundle, "DefinitionPackage", "fixture-nim")
        package["dependencies"] = [{"id":package["id"], "revision":1}]
        self.invalid("Cyclic DefinitionPackage")

    def test_concepts_resolve_in_exact_bgsm_release(self):
        get(self.bundle, "BGSMRelease")["concepts"].pop()
        self.invalid("absent from formalization BGSM")

    def test_file_digest_and_path_boundary(self):
        file = get(self.bundle, "DefinitionPackage")["files"][0]
        file["sha256"] = "0" * 64
        self.invalid("File digest mismatch")
        file["path"] = "../private.txt"
        self.invalid("Schema error")

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sources").symlink_to(FIXTURES / "sources", target_is_directory=True)
            with self.assertRaisesRegex(ContractError, "inside bundle root"):
                validate_bundle(self.bundle, root, allow_fixtures=True)

    def test_review_digest_binds_prose(self):
        get(self.bundle, "RulebookEdition")["label"] = "Unreviewed change"
        with self.assertRaisesRegex(ContractError, "Review digest mismatch"):
            self.validate()

    def test_manifest_digest_binds_unreviewed_metadata(self):
        get(self.bundle, "Game")["title"] = "Changed"
        with self.assertRaisesRegex(ContractError, "Manifest digest mismatch"):
            self.validate()

    def test_manifest_has_no_silent_omissions(self):
        self.bundle["publication"]["manifest"].pop()
        self.bundle["publication"]["review"]["reviewedDigest"] = reviewed_digest(self.bundle["publication"])
        with self.assertRaisesRegex(ContractError, "exactly the supplied records"):
            self.validate()

    def next_publication(self):
        previous = copy.deepcopy(self.bundle)
        self.bundle["publication"]["id"] = "fixture-next-release"
        self.bundle["publication"]["previous"] = {"id":previous["publication"]["id"], "sha256":digest(previous["publication"])}
        return previous

    def test_old_records_preserved_on_new_publication(self):
        previous = self.next_publication()
        seal(self.bundle)
        self.validate(previous=previous)
        get(self.bundle, "Game")["title"] = "Reused immutable revision"
        seal(self.bundle)
        with self.assertRaisesRegex(ContractError, "Immutable record changed"):
            self.validate(previous=previous)

    def test_new_edition_revision_keeps_old_pins(self):
        previous = self.next_publication()
        older = get(self.bundle, "RulebookEdition", "nim-one-two")
        newer = copy.deepcopy(older)
        newer.update(revision=2, previous={"id":older["id"], "revision":1}, change={"kind":"editorial", "summary":"Improve label"}, label="Clearer label")
        self.bundle["records"].append(newer)
        game = copy.deepcopy(get(self.bundle, "Game", "nim-normal-play"))
        game["revision"] = 2
        game["defaultEdition"]["revision"] = 2
        self.bundle["records"].append(game)
        self.bundle["publication"]["games"][1]["revision"] = 2
        seal(self.bundle)
        self.validate(previous=previous)
        self.assertEqual(get(self.bundle, "Formalization")["edition"]["revision"], 1)

    def test_withdrawal_retains_notice_without_dangling_defaults(self):
        previous = self.next_publication()
        removed = get(self.bundle, "Formalization", "fixture-rps-mapping")
        self.bundle["records"].remove(removed)
        seal(self.bundle)
        with self.assertRaisesRegex(ContractError, "missing without withdrawal"):
            self.validate(previous=previous)
        self.bundle["publication"]["withdrawals"] = [{"record":manifest_entry(removed), "reason":"Fixture mapping withdrawn; readable edition retained."}]
        seal(self.bundle)
        self.validate(previous=previous)

    def test_new_bgsm_can_reformalize_nim_without_rewriting_any_game(self):
        previous = self.next_publication()
        old_version = get(self.bundle, "BGSMRelease")["version"]
        new_version = "0.0.0-fixture.2"
        for name in ["fixture-nim", "fixture-conformance"]:
            package = copy.deepcopy(get(self.bundle, "DefinitionPackage", name))
            package.update(revision=2, bgsm=new_version)
            self.bundle["records"].append(package)
        model = copy.deepcopy(get(self.bundle, "BGSMRelease"))
        model.update(version=new_version, previous=old_version,
                     changelog="Second fictional model, to test independent version evolution.")
        model["conformance"]["revision"] = 2
        self.bundle["records"].append(model)
        mapping = copy.deepcopy(get(self.bundle, "Formalization", "fixture-nim-mapping"))
        mapping.update(revision=2, bgsm=new_version)
        mapping["package"]["revision"] = 2
        for row in mapping["coverage"]:
            for link in row["definitions"]:
                link["package"]["revision"] = 2
        self.bundle["records"].append(mapping)
        seal(self.bundle)
        result = self.validate(previous=previous)
        self.assertEqual(len(result["formalCoverage"]), 3)
        for kind in ["Game", "RulebookEdition"]:
            self.assertEqual([r for r in previous["records"] if r["kind"] == kind],
                             [r for r in self.bundle["records"] if r["kind"] == kind])

    def test_previous_release_is_required(self):
        self.next_publication()
        seal(self.bundle)
        with self.assertRaisesRegex(ContractError, "Previous publication is required"):
            self.validate()

    def evidence(self, result="pass"):
        formalization = get(self.bundle, "Formalization")
        return {"kind":"VerificationRecord", "id":"fixture-evidence", "revision":1, "testOnly":True,
                "formalization":{"id":formalization["id"],"revision":1}, "subjectDigest":digest(formalization),
                "implementation":{"id":"fixture-checker","version":"0.0.0-fixture.1","buildDigest":"1"*64},
                "suite":get(self.bundle,"DefinitionPackage")["files"][0], "method":"structural",
                "scope":"Synthetic evidence, no execution claim", "result":result,
                "run":{"at":"2026-11-07T00:00:00Z","url":"https://example.invalid/fixture-run"}}

    def test_verification_result_does_not_relabel_formal_coverage(self):
        for result in ["pass", "fail", "unknown"]:
            bundle = copy.deepcopy(self.bundle)
            bundle["records"].append(self.evidence(result))
            seal(bundle)
            self.assertEqual(self.validate(bundle)["formalCoverage"]["Formalization/fixture-nim-mapping/1"], "complete")

    def test_bounded_verification_needs_bounds_and_exact_subject(self):
        evidence = self.evidence()
        self.bundle["records"].append(evidence)
        evidence["method"] = "bounded-exhaustive"
        self.invalid("Schema error")
        evidence["bounds"] = "Fictional finite configuration; this test is not actual exploration."
        evidence["subjectDigest"] = "0"*64
        self.invalid("does not match its formalization digest")

    def test_failed_verification_blocks_recommendation(self):
        self.bundle["records"].append(self.evidence("fail"))
        self.bundle["publication"]["recommendedFormalizations"] = [{"id":"fixture-nim-mapping","revision":1}]
        self.invalid("failed verification")

    def test_build_artifact_binds_input_output_and_source_map(self):
        formalization = get(self.bundle, "Formalization")
        artifact = {"kind":"BuildArtifact", "id":"fixture-artifact", "revision":1, "testOnly":True,
                    "formalization":{"id":formalization["id"],"revision":1}, "inputDigest":digest(formalization),
                    "compiler":{"id":"fixture-compiler","version":"0.0.0-fixture.1","buildDigest":"1"*64},
                    "output":get(self.bundle,"DefinitionPackage")["files"][0],
                    "sourceMap":[{"rule":"players","definition":{"package":{"id":"fixture-nim","revision":1},"definition":"players"}}]}
        self.bundle["records"].append(artifact)
        seal(self.bundle)
        self.validate()
        artifact["sourceMap"][0]["rule"] = "absent"
        self.invalid("source map names a missing rule")

    def test_json_duplicate_keys_and_nonfinite_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"invalid.json"
            for content in ['{"id":1,"id":2}', '{"value":NaN}']:
                path.write_text(content)
                with self.assertRaises(ContractError):
                    load_json(path)


if __name__ == "__main__":
    unittest.main()
