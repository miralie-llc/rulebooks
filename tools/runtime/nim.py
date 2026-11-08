"""Independently check the candidate 1/2-heap Nim definition; never claim acceptance."""
from collections import deque
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from tools.runtime.engine import ROOT, canonical, compile_program, inspection, fingerprint, need, IllegalIntent


def expected_intents(state,actor):
    if actor!=state['turn'] or sum(state['heaps'])==0:return []
    return [{'action':'take','params':{'heap':heap,'amount':amount}}
            for heap,count in enumerate(state['heaps']) for amount in range(1,count+1)]


def expected_after(state,actor,intent):
    heaps=state['heaps'].copy();heaps[intent['params']['heap']]-=intent['params']['amount']
    return {'heaps':heaps,'turn':'b' if actor=='a' else 'a','winner':actor if sum(heaps)==0 else None}


def verify_nim(source,edition):
    game=compile_program(source)
    need(edition['id']=='nim-one-two' and edition['revision']==1,'Wrong Nim rulebook target')
    rule_ids={r['id'] for section in edition['sections'] for r in section['rules']}
    need({link['rule'] for link in game.program['sourceMap']}==rule_ids,'Every exact readable rule needs a source mapping')
    initial={'heaps':[1,2],'turn':'a','winner':None}
    need(game.initial()==initial,'Wrong starting configuration')
    queue=deque([initial]);seen={};edges=0;rejections=0
    while queue:
        state=queue.popleft();key=canonical(state)
        if key in seen:continue
        seen[key]=state;before=copy.deepcopy(state)
        terminal=sum(state['heaps'])==0
        outcome={'terminal':terminal,'winners':[state['winner']] if terminal else []}
        need(game.outcome(state)==outcome,'Outcome mismatch')
        for actor in ['a','b']:
            expected=expected_intents(state,actor)
            need(sorted(map(canonical,game.intents(state,actor)))==sorted(map(canonical,expected)),'Legal-intent set mismatch')
            need(game.observe(state,actor)==state,'Public observation mismatch')
            for heap in [-1,0,1,2]:
                for amount in [-1,0,1,2,3,True]:
                    intent={'action':'take','params':{'heap':heap,'amount':amount}}
                    valid=canonical(intent) in {canonical(i) for i in expected}
                    need(game.legal(state,actor,intent)==valid,'Illegal intent accepted or valid intent rejected')
                    if not valid:
                        try:game.resolve(state,actor,intent)
                        except IllegalIntent:rejections+=1
                        else:raise ValueError('Rejected intent resolved')
            for intent in expected:
                rows=game.resolve(state,actor,intent)
                need(len(rows)==1 and rows[0]['probability']==Fraction(1),'Nim must resolve deterministically')
                after=game.reduce(state,actor,intent,rows[0]['event'])
                predicted=expected_after(state,actor,intent)
                need(after==predicted,'Transition mismatch')
                need(game.reduce(state,actor,intent,rows[0]['event'])==predicted,'Reduction not deterministic')
                queue.append(predicted);edges+=1
        need(state==before,'State mutated during verification')
    artifact=inspection(game)
    report={'kind':'ReferenceVerification','schemaVersion':'0.1.0','purpose':'draft-game-definition','result':'pass',
            'method':'bounded-exhaustive','sampling':False,'implementation':artifact['implementation'],
            'subjectDigest':artifact['sourceDigest'],'rulebook':{'id':edition['id'],'revision':edition['revision'],'sha256':fingerprint(edition)},
            'suite':{'id':'nim-independent-reachable-states','version':'0.1.0','runnerDigest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()} ,
            'scope':'Normal-play Nim, heaps [1,2], player a first, public information; all reachable states and legal transitions.',
            'bounds':{'initialHeaps':[1,2],'reachableStates':len(seen),'legalTransitions':edges,'rejectedIntents':rejections,'terminalStates':sum(sum(s['heaps'])==0 for s in seen.values())},
            'coverage':[{'rule':rule,'status':'candidate-represented'} for rule in sorted(rule_ids)],
            'states':[seen[key] for key in sorted(seen)]}
    return artifact,report


def build_nim(root=ROOT):
    source_bytes=(root/'data/definitions/nim-one-two/1.json').read_bytes()
    edition_bytes=(root/'data/catalog/records/RulebookEdition-nim-one-two-1.json').read_bytes()
    source=json.loads(source_bytes);edition=json.loads(edition_bytes)
    artifact,report=verify_nim(source,edition)
    prefix='public/data/candidates/nim/'+fingerprint({'source':hashlib.sha256(source_bytes).hexdigest(),'report':report})+'/'
    outputs={prefix+'source.json':source_bytes,prefix+'inspection.json':canonical(artifact),prefix+'verification.json':canonical(report),prefix+'rulebook.json':edition_bytes}
    entry={'source':source,'rulebook':edition,'inspection':artifact,'verification':report,'files':[{'url':'/data/'+name.removeprefix('public/data/'),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for name,raw in outputs.items()]}
    return outputs,entry


if __name__=='__main__':
    _,entry=build_nim();print(json.dumps(entry['verification'],sort_keys=True))
