import copy
import json
from pathlib import Path
import unittest
from tools.editorial_diff import record_diff, definition_diffs, behavior
ROOT=Path(__file__).resolve().parents[1]


class EditorialDiffTests(unittest.TestCase):
    def test_rule_changes_keep_exact_ids_digests_and_citations(self):
        file=ROOT/'data/catalog/records/RulebookEdition-nim-one-two-1.json'
        before=json.loads(file.read_text());after=copy.deepcopy(before)
        after['sections'][0]['rules'][0]['statement']='Changed statement for diff test only.'
        name=file.relative_to(ROOT).as_posix()
        changes=record_diff({name:file.read_bytes()},{name:json.dumps(after).encode()})
        self.assertEqual(len(changes),1)
        self.assertEqual(changes[0]['rules'][0]['id'],'last-counter')
        self.assertNotEqual(changes[0]['beforeDigest'],changes[0]['afterDigest'])
        self.assertEqual(changes[0]['rules'][0]['before']['origin'],changes[0]['rules'][0]['after']['origin'])

    def test_behavior_comparison_detects_changed_winner_and_unchanged_formatting(self):
        path='data/definitions/nim-one-two/1.json';raw=(ROOT/path).read_bytes();source=json.loads(raw)
        formatting=json.dumps(source).encode()
        unchanged=definition_diffs({path:raw},{path:formatting})[0]
        self.assertTrue(unchanged['behaviorEquivalentWithinExploredBounds'])
        source['actions'][0]['effects']['winner']='a'
        changed=definition_diffs({path:raw},{path:json.dumps(source).encode()})[0]
        self.assertFalse(changed['behaviorEquivalentWithinExploredBounds'])
        self.assertGreater(changed['changedStates'],0)

    def test_limits_never_claim_complete_equivalence(self):
        source=json.loads((ROOT/'data/definitions/nim-one-two/1.json').read_text())
        result=behavior(source,limit=2)
        self.assertFalse(result['complete'])
        self.assertIn('limit',result['reason'])
