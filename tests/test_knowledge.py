"""Draft inference/provenance and editorial projection tests, not game implementations."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

from tools.check_repository import CheckError, snapshot, validate_candidate
from tools.validate_knowledge import (
    ROOT, SCHEMA, ContractError, digest, pin, project, reviewed_digest,
    validate_draft, validate_fixture, validate_handoffs, verify_trace, write_projection,
)
from tools.validate_publication import load_json, manifest_entry, validate_bundle

FIXTURES = ROOT / 'tests/fixtures/knowledge'


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.load('chess')

    def load(self, game):
        folder = FIXTURES / game
        self.draft = load_json(folder / 'draft.json')
        self.review = load_json(folder / 'review.json')
        self.sources = [load_json(p) for p in sorted(folder.glob('*.source.json'))]
        self.handoffs = [load_json(p) for p in sorted(folder.glob('*.handoff.json'))]

    def seal(self):
        self.review['draft'] = pin(self.draft)
        self.review['review']['reviewedDigest'] = reviewed_digest(self.review)

    def project(self):
        return project(self.draft, self.review, self.sources, handoffs=self.handoffs, allow_fixtures=True)

    def test_schema_and_three_expected_projections(self):
        Draft202012Validator.check_schema(SCHEMA)
        for game in ['chess', 'nim-normal-play', 'rock-paper-scissors']:
            with self.subTest(game=game):
                self.assertGreater(validate_fixture(FIXTURES / game), 0)

    def test_original_nim_needs_no_files_or_external_source_records(self):
        self.load('nim-normal-play')
        edition, trace = self.project()
        self.assertEqual(edition['readingStatus'], 'complete')
        self.assertEqual(trace['handoffs'], [])
        self.assertEqual(trace['sourceRecords'], [])
        self.assertEqual(len(edition['sections'][0]['rules']), 8)
        self.assertTrue(verify_trace(trace, edition, allow_fixtures=True))

    def test_wrong_inference_rejected_but_evidence_and_open_questions_retained(self):
        edition, trace = self.project()
        self.assertNotIn('rook-frozen', [r['id'] for s in edition['sections'] for r in s['rules']])
        self.assertIn('rook-frozen', [r['id'] for r in trace['draft']['rules']])
        self.assertEqual(len(trace['draft']['questions']), 2)
        self.assertIn(self.review['questions'][1]['publicNote'], edition['scope']['excludes'])
        self.assertNotIn('artifact', json.dumps(edition))
        self.assertNotIn('observation', json.dumps(edition))

    def test_editor_can_reword_without_erasing_producer_statement(self):
        self.review['decisions'][0]['output']['statement'] = 'White takes the first turn; thereafter the players alternate.'
        self.seal()
        edition, trace = self.project()
        self.assertNotEqual(edition['sections'][0]['rules'][0]['statement'], trace['draft']['rules'][0]['statement'])
        self.assertTrue(verify_trace(trace, edition, allow_fixtures=True))

    def test_fixture_not_accepted_as_real_input(self):
        with self.assertRaisesRegex(ContractError, 'Fixture'):
            validate_draft(self.draft)

    def test_exact_draft_and_decision_binding(self):
        self.draft['rules'][0]['statement'] += ' Changed.'
        with self.assertRaisesRegex(ContractError, 'exact draft'):
            self.project()
        self.seal()
        self.review['decisions'][0]['reason'] = 'Changed review without resealing.'
        with self.assertRaisesRegex(ContractError, 'decision digest'):
            self.project()

    def test_missing_duplicate_and_dangling_references(self):
        for mutate in [
            lambda d: d['rules'].append(copy.deepcopy(d['rules'][0])),
            lambda d: d['rules'][0]['evidence'][0].update(evidenceId='missing'),
            lambda d: d['evidence'][0].update(runId='missing'),
            lambda d: d['rules'][0].update(entityIds=['missing']),
        ]:
            with self.subTest(mutation=mutate):
                self.load('chess');mutate(self.draft)
                with self.assertRaises(ContractError):
                    validate_draft(self.draft, allow_fixtures=True)

    def test_play_observation_cannot_be_labeled_explicit_rule(self):
        self.draft['rules'][2]['basis'] = 'explicit'
        with self.assertRaisesRegex(ContractError, 'document assertions'):
            validate_draft(self.draft, allow_fixtures=True)

    def test_inference_requires_rationale_and_acyclic_premises(self):
        del self.draft['rules'][2]['rationale']
        with self.assertRaisesRegex(ContractError, 'structure'):
            validate_draft(self.draft, allow_fixtures=True)
        self.load('chess')
        self.draft['rules'][2]['premises'] = ['rook-frozen']
        with self.assertRaisesRegex(ContractError, 'Circular'):
            validate_draft(self.draft, allow_fixtures=True)

    def test_contradiction_cannot_disappear_without_question(self):
        self.draft['questions'] = self.draft['questions'][1:]
        with self.assertRaisesRegex(ContractError, 'conflict question'):
            validate_draft(self.draft, allow_fixtures=True)

    def test_questions_and_rules_require_complete_decision_inventory(self):
        for field in ['questions', 'decisions']:
            with self.subTest(field=field):
                self.load('chess');self.review[field].pop();self.seal()
                with self.assertRaisesRegex(ContractError, 'account for every'):
                    self.project()

    def test_deferred_question_must_be_visible_and_block_completeness(self):
        self.review['target']['scope']['excludes'].pop();self.seal()
        with self.assertRaisesRegex(ContractError, 'visible scope'):
            self.project()
        self.load('chess');self.review['target']['readingStatus'] = 'complete';self.seal()
        with self.assertRaisesRegex(ContractError, 'completeness question'):
            self.project()

    def test_open_publication_blocker_prevents_affected_acceptance(self):
        self.load('nim-normal-play')
        self.draft['questions'] = [{'id':'unclear-ending','kind':'ambiguity','question':'Who wins?', 'blocks':'publication','ruleIds':['last-wins'],'evidenceIds':[],'runId':'fixture-run'}]
        self.review['questions'] = [{'questionId':'unclear-ending','decision':'deferred','reason':'Not established.','publicNote':'Winning condition is unresolved.'}]
        self.review['target']['scope']['excludes'].append('Winning condition is unresolved.')
        self.seal()
        with self.assertRaisesRegex(ContractError, 'publication blocker'):
            self.project()

    def test_mapped_public_source_edition_and_citations_cannot_drift(self):
        self.sources[0]['edition'] = {'label':'Another document edition'}
        with self.assertRaisesRegex(ContractError, 'document edition'):
            self.project()
        self.load('chess')
        self.review['decisions'][0]['output']['origin']['citations'][0]['source']['revision'] = 2
        self.seal()
        with self.assertRaisesRegex(ContractError, 'source pins'):
            self.project()

    def test_external_support_cannot_be_replaced_by_editorial_attribution(self):
        self.review['decisions'][0]['output']['origin'] = {'kind':'editorial','attribution':'We decided this.'}
        self.seal()
        with self.assertRaisesRegex(ContractError, 'external attribution'):
            self.project()

    def test_supporting_premise_provenance_reaches_public_citations(self):
        first, second = self.draft['rules'][:2]
        second.update(basis='inferred', rationale='Synthetic inference for reference closure testing.', evidence=[], premises=[first['id']])
        # This is a structural fixture mutation, not a valid deduction about chess.
        self.seal()
        edition, trace = self.project()
        self.assertEqual(edition['sections'][0]['rules'][1]['origin']['citations'][0]['source']['id'], self.sources[0]['id'])
        self.review['decisions'][0] = {'ruleId':first['id'],'decision':'reject','reason':'Premise rejected.'};self.seal()
        with self.assertRaisesRegex(ContractError, 'unaccepted premise'):
            self.project()

    def test_tampered_artifact_pin_and_missing_handoff_rejected(self):
        with self.assertRaisesRegex(ContractError, 'Missing evidence'):
            project(self.draft, self.review, self.sources, allow_fixtures=True)
        self.handoffs[0]['original']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ContractError, 'manifest digest'):
            validate_handoffs(self.draft, self.handoffs)
        self.load('chess')
        self.draft['sources'][0]['artifacts'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ContractError, 'artifact path/digest'):
            validate_handoffs(self.draft, self.handoffs)

    def test_pdf_and_derivative_share_source_but_have_distinct_evidence_artifacts(self):
        source = self.draft['sources'][0]
        original = source['artifacts'][0]
        manifest = next(h for h in self.handoffs if h['handoffId'] == original['handoffId'])
        derivative = {**manifest['original'], 'path':'extracts/ocr.txt'}
        manifest['derived'] = [{'file':derivative, 'metadata':{
            'id':'ocr', 'revision':1, 'extractor':{'name':'fixture-copy','version':'1.0.0','options':{}},
            'anchors':[{'locator':'Synthetic teaching sheet','startByte':0,'endByte':derivative['size']}],
        }}]
        source['artifacts'].append({**original, 'id':'ocr', 'path':derivative['path']})
        for artifact in source['artifacts']:
            artifact['manifestDigest'] = digest(manifest)
        self.draft['evidence'][0].update(artifactId='ocr', locator={'kind':'bytes','startByte':0,'endByte':10})
        self.seal()
        edition, trace = self.project()
        self.assertEqual(len(trace['draft']['sources'][0]['artifacts']), 2)
        self.assertTrue(verify_trace(trace, edition, allow_fixtures=True))
        del self.draft['evidence'][0]['artifactId']
        with self.assertRaisesRegex(ContractError, 'unknown artifact'):
            validate_draft(self.draft, allow_fixtures=True)

    def test_source_acquisition_identity_and_publisher_edition_checked(self):
        self.handoffs[0]['capture']['sourceId'] = 'different-source'
        for source in self.draft['sources']:
            for artifact in source.get('artifacts', []):
                if artifact['handoffId'] == self.handoffs[0]['handoffId']:
                    artifact['manifestDigest'] = digest(self.handoffs[0])
        with self.assertRaisesRegex(ContractError, 'identity/edition'):
            validate_handoffs(self.draft, self.handoffs)
        self.load('chess');self.draft['game']['publisherEdition'] = 'Second edition'
        with self.assertRaisesRegex(ContractError, 'publisher edition'):
            validate_handoffs(self.draft, self.handoffs)
        for source in self.draft['sources']:
            source['applicability'] = 'Comparative research only; applicability to the second edition remains subject to editorial review.'
        self.assertEqual(validate_handoffs(self.draft, self.handoffs), 2)

    def test_artifact_paths_and_evidence_spans_checked(self):
        self.draft['sources'][0]['artifacts'][0]['path'] = '../elsewhere.txt'
        with self.assertRaisesRegex(ContractError, 'relative path'):
            validate_draft(self.draft, allow_fixtures=True)
        self.load('chess')
        self.draft['evidence'][0]['locator'] = {'kind':'bytes','startByte':0,'endByte':999999}
        with self.assertRaisesRegex(ContractError, 'exceeds'):
            validate_handoffs(self.draft, self.handoffs)
        self.load('chess')
        self.draft['evidence'][2]['locator']['endMs'] = 1
        with self.assertRaisesRegex(ContractError, 'time span'):
            validate_draft(self.draft, allow_fixtures=True)

    def test_action_conditions_keep_rule_provenance(self):
        self.load('nim-normal-play')
        action = next(e for e in self.draft['entities'] if 'action' in e)
        action['action']['conditionRuleIds'] = ['unknown-condition']
        with self.assertRaisesRegex(ContractError, 'supporting rule links'):
            validate_draft(self.draft, allow_fixtures=True)

    def test_unknown_fields_future_schema_and_floating_tool_version_rejected(self):
        for mutate in [lambda d:d.update(arbitrary={}), lambda d:d.update(schemaVersion='0.2.0'), lambda d:d['runs'][0]['tool'].update(version='latest')]:
            self.load('chess');mutate(self.draft)
            with self.assertRaises(ContractError):
                validate_draft(self.draft, allow_fixtures=True)

    def test_new_draft_revision_preserves_identity_and_trusted_predecessor(self):
        previous = copy.deepcopy(self.draft)
        self.draft.update(revision=2, previous=pin(previous))
        self.draft['rules'][0]['statement'] += ' (Reworded.)'
        self.assertTrue(validate_draft(self.draft, previous=previous, allow_fixtures=True)['historyChecked'])
        self.draft['game']['id'] = 'another-game'
        with self.assertRaisesRegex(ContractError, 'game identity'):
            validate_draft(self.draft, previous=previous, allow_fixtures=True)

    def test_trace_tamper_and_output_tamper_detected(self):
        edition, trace = self.project()
        edition['sections'][0]['rules'][0]['statement'] = 'Unreviewed replacement.'
        with self.assertRaisesRegex(ContractError, 'trace/output'):
            verify_trace(trace, edition, allow_fixtures=True)
        edition, trace = self.project()
        trace['draft']['questions'].pop()
        with self.assertRaises(ContractError):
            verify_trace(trace, edition, allow_fixtures=True)

    def test_projected_edition_fits_actual_publication_validator(self):
        edition, trace = self.project()
        bundle = load_json(ROOT / 'tests/fixtures/publication/first-games.json')
        game = {'kind':'Game','testOnly':True,'id':'chess','revision':1,'title':'Chess fixture','defaultEdition':{'id':edition['id'],'revision':1}}
        bundle['records'] = [game, edition, *self.sources]
        pub = bundle['publication']
        pub['games'] = [{'id':'chess','revision':1}]
        pub.pop('recommendedFormalizations', None)
        pub['manifest'] = [manifest_entry(r) for r in bundle['records']]
        pub['review']['reviewedDigest'] = reviewed_digest(pub)
        self.assertEqual(validate_bundle(bundle, FIXTURES, allow_fixtures=True)['games'], 1)

    def test_private_trace_cannot_enter_repository(self):
        edition, trace = self.project()
        files = snapshot(ROOT)
        files['data/unreviewed.json'] = json.dumps(trace).encode()
        with self.assertRaisesRegex(CheckError, 'Private knowledge'):
            validate_candidate(files)

    def test_output_is_private_new_directory_and_never_overwritten(self):
        self.load('nim-normal-play')
        edition, trace = self.project()
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'projection'
            write_projection(target, edition, trace)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual((target / 'trace.json').stat().st_mode & 0o777, 0o600)
            self.assertTrue(verify_trace(load_json(target / 'trace.json'), load_json(target / 'edition.json'), allow_fixtures=True))
            with self.assertRaises(FileExistsError):
                write_projection(target, edition, trace)

    def test_cli_validates_fixture_and_rejects_unmarked_use(self):
        command = [sys.executable, str(ROOT / 'tools/validate_knowledge.py'), 'validate', '--draft', str(FIXTURES / 'nim-normal-play/draft.json')]
        denied = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(denied.returncode, 0)
        accepted = subprocess.run([*command, '--allow-fixtures'], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)['rules'], 8)

    def test_cli_chess_projection_with_source_and_artifact_handoffs(self):
        folder = FIXTURES / 'chess'
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'projection'
            command = [sys.executable, str(ROOT / 'tools/validate_knowledge.py'), 'project',
                       '--draft', str(folder / 'draft.json'), '--review', str(folder / 'review.json'),
                       '--output-dir', str(target), '--allow-fixtures']
            for file in sorted(folder.glob('*.handoff.json')):
                command.extend(['--handoff', str(file)])
            for file in sorted(folder.glob('*.source.json')):
                command.extend(['--source', str(file)])
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['published'])
            self.assertEqual(load_json(target / 'edition.json'), load_json(folder / 'expected-edition.json'))
            self.assertTrue(verify_trace(load_json(target / 'trace.json'), load_json(target / 'edition.json'), allow_fixtures=True))


if __name__ == '__main__':
    unittest.main()
