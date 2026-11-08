import copy
import json
from pathlib import Path
import unittest
from tools.runtime.specimens import build_specimens, verify_case
from tools.runtime.engine import ProgramError
ROOT=Path(__file__).resolve().parents[1]


class SpecimenTests(unittest.TestCase):
    def test_actual_evidence_and_artifacts_are_repeatable(self):
        files,index=build_specimens()
        self.assertEqual((files,index),build_specimens())
        self.assertEqual(len(index['entries']),2)
        for entry in index['entries']:
            report=entry['verification']
            self.assertEqual(report['result'],'pass')
            self.assertFalse(report['sampling'])
            self.assertEqual(report['purpose'],'developer-fixture')
            self.assertEqual(report['bounds']['events'],2)
            self.assertEqual(report['subjectDigest'],entry['inspection']['sourceDigest'])
            self.assertIn('runnerDigest',report['suite'])
            self.assertEqual(len(entry['inspection']['sourceMap']),5)

    def test_weight_or_effect_regressions_fail_the_independent_oracle(self):
        source=json.loads((ROOT/'tests/fixtures/runtime/coin.json').read_text())
        case=json.loads((ROOT/'tests/fixtures/runtime/specimens.json').read_text())['cases'][0]
        bad=copy.deepcopy(source);bad['actions'][0]['resolve']['chance'][0]['weight']=2
        with self.assertRaises(ProgramError):verify_case(bad,case)
        bad=copy.deepcopy(source);bad['actions'][0]['effects']['face']='heads'
        with self.assertRaises(ProgramError):verify_case(bad,case)
