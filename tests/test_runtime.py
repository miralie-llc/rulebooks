"""Independent expected behavior and negative tests for the bounded reference engine."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import unittest
from tools.runtime.engine import compile_program, inspection, evaluate, ProgramError, IllegalIntent

ROOT=Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.source=json.loads((ROOT/'tests/fixtures/runtime/counter.json').read_text())
        self.game=compile_program(self.source)
        self.intent={'action':'take','params':{'amount':1}}

    def test_turn_ownership_and_finite_legal_intents(self):
        state=self.game.initial()
        self.assertEqual(self.game.intents(state,'a'),[self.intent,{'action':'take','params':{'amount':2}}])
        self.assertEqual(self.game.intents(state,'b'),[])
        self.assertEqual(self.game.outcome(state),{'terminal':False,'winners':[]})

    def test_resolution_reduction_observation_and_outcome_are_pure(self):
        state=self.game.initial();before=copy.deepcopy(state)
        event=self.game.resolve(state,'a',self.intent)[0]
        self.assertEqual(event,{'event':{'amount':1,'actor':'a'},'probability':Fraction(1)})
        after=self.game.reduce(state,'a',self.intent,event['event'])
        self.assertEqual(after,{'remaining':1,'turn':'b','winner':None})
        final=self.game.reduce(after,'b',self.intent,{'amount':1,'actor':'b'})
        self.assertEqual(self.game.outcome(final),{'terminal':True,'winners':['b']})
        self.assertEqual(self.game.intents(final,'a'),[])
        self.assertEqual(state,before)
        observation=self.game.observe(after,'a');observation['remaining']=999
        self.assertEqual(after['remaining'],1)
        self.assertEqual(self.game.reduce(state,'a',self.intent,event['event']),after)

    def test_rejected_intents_and_forged_events_never_mutate_state(self):
        state=self.game.initial();before=copy.deepcopy(state)
        for intent in [None,{}, {'action':'other','params':{}},{'action':'take','params':{'amount':True}}, {'action':'take','params':{'amount':3}}, {'action':'take','params':{'amount':1,'extra':0}}]:
            with self.subTest(intent=intent),self.assertRaises(IllegalIntent):self.game.resolve(state,'a',intent)
        with self.assertRaises(IllegalIntent):self.game.resolve(state,'b',self.intent)
        with self.assertRaises(ProgramError):self.game.reduce(state,'a',self.intent,{'amount':2,'actor':'a'})
        self.assertEqual(state,before)

    def test_effects_all_read_the_pre_state(self):
        state=self.game.initial();intent={'action':'take','params':{'amount':2}}
        after=self.game.reduce(state,'a',intent,{'amount':2,'actor':'a'})
        self.assertEqual(after['winner'],'a')
        self.assertEqual(self.game.outcome(after),{'terminal':True,'winners':['a']})

    def test_compilation_detaches_input_and_rejects_unknown_pins_and_code(self):
        self.source['initial']['remaining']=9
        self.assertEqual(self.game.initial()['remaining'],2)
        for mutate in [lambda p:p.update(bgsm='latest'),lambda p:p['language'].update(version='1.0.0'),
                       lambda p:p['capabilities'].append('hidden-information'),lambda p:p.update(imports=['host.py']),
                       lambda p:p['actions'][0].update(legal={'op':'eval','args':['anything']})]:
            value=copy.deepcopy(self.source);mutate(value)
            with self.assertRaises(ProgramError):compile_program(value)

    def test_phase_variables_and_source_maps_are_validated(self):
        for mutate in [lambda p:p['actions'][0].update(legal={'var':'event.amount'}),
                       lambda p:p['actions'][0]['effects'].update(remaining={'var':'params.amount'}),
                       lambda p:p['actions'][0]['effects'].update(extra=1),
                       lambda p:p['sourceMap'][0].update(node='/missing'),
                       lambda p:p['actions'][0].update(legal={'var':'state.missing'})]:
            value=copy.deepcopy(self.source);mutate(value)
            with self.assertRaises(ProgramError):compile_program(value)

    def test_finite_limits_and_runtime_types_fail_explicitly(self):
        value=copy.deepcopy(self.source);value['initial']['remaining']=1.5
        with self.assertRaises(ProgramError):compile_program(value)
        value=copy.deepcopy(self.source);value['actions'][0]['parameters']={k:list(range(64)) for k in ['a','b','c']}
        with self.assertRaises(ProgramError):compile_program(value)
        with self.assertRaises(ProgramError):evaluate({'op':'add','args':[True,1]}, {})
        with self.assertRaises(ProgramError):evaluate({'op':'get','args':[[1],-1]}, {})
        with self.assertRaises(ProgramError):self.game.observe(self.game.initial(),'outsider')
        with self.assertRaises(ProgramError):self.game.outcome({'remaining':0})

    def test_short_circuit_does_not_evaluate_unused_branch(self):
        self.assertFalse(evaluate({'op':'and','args':[False,{'op':'get','args':[[],0]}]},{}))
        self.assertEqual(evaluate({'op':'if','args':[True,1,{'op':'get','args':[[],0]}]},{}),1)

    def test_inspection_is_deterministic_and_records_all_independent_pins(self):
        first=inspection(self.game);second=inspection(compile_program(self.game.program))
        self.assertEqual(first,second)
        self.assertEqual(first['implementation']['version'],'0.1.0')
        self.assertEqual(first['program']['library']['version'],'0.1.0')
        self.assertEqual(len(first['sourceDigest']),64)
        self.assertEqual(first['sourceMap'],self.source['sourceMap'])

    def test_exact_chance_and_duplicate_outcome_coalescing(self):
        self.source['capabilities'].append('exact-chance')
        event={'op':'object','args':[['amount',1],['actor',{'var':'actor'}]]}
        other={'op':'object','args':[['amount',2],['actor',{'var':'actor'}]]}
        self.source['actions'][0]['resolve']={'chance':[{'weight':1,'value':event},{'weight':1,'value':event},{'weight':4,'value':other}]}
        game=compile_program(self.source)
        rows=game.resolve(game.initial(),'a',self.intent)
        self.assertEqual({r['event']['amount']:r['probability'] for r in rows},{1:Fraction(1,3),2:Fraction(2,3)})
        self.assertEqual(sum(r['probability'] for r in rows),1)
        for weight in [0,-1,True,0.5]:
            self.source['actions'][0]['resolve']['chance'][0]['weight']=weight
            with self.assertRaises(ProgramError):compile_program(self.source)
