import copy
import json
from pathlib import Path
import unittest
from tools.runtime.nim import build_nim, verify_nim
from tools.runtime.engine import ProgramError
ROOT=Path(__file__).resolve().parents[1]


class NimTests(unittest.TestCase):
    def test_all_reachable_behavior_and_rejections_match_independent_oracle(self):
        files,entry=build_nim();report=entry['verification']
        self.assertEqual(report['bounds'],{'initialHeaps':[1,2],'reachableStates':8,'legalTransitions':10,'rejectedIntents':374,'terminalStates':2})
        self.assertEqual(report['purpose'],'draft-game-definition')
        self.assertEqual(report['rulebook']['id'],'nim-one-two')
        self.assertEqual(len(report['coverage']),7)
        self.assertEqual((files,entry),build_nim())

    def test_rule_or_transition_regressions_fail(self):
        source=json.loads((ROOT/'data/definitions/nim-one-two/1.json').read_text())
        edition=json.loads((ROOT/'data/catalog/records/RulebookEdition-nim-one-two-1.json').read_text())
        for mutate in [lambda p:p['initial'].update(heaps=[1,3]),
                       lambda p:p['actions'][0]['effects'].update(turn='a'),
                       lambda p:p['actions'][0]['effects'].update(winner='a'),
                       lambda p:p['sourceMap'].pop(0)]:
            wrong=copy.deepcopy(source);mutate(wrong)
            with self.assertRaises(ProgramError):verify_nim(wrong,edition)
