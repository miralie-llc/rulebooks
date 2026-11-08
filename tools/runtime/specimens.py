"""Execute explicit developer specimens and emit deterministic evidence, never game approvals."""
import copy
import hashlib
import json
from pathlib import Path
from tools.runtime.engine import ROOT, canonical, compile_program, inspection, fingerprint, need, IllegalIntent


def verify_case(source,case):
    game=compile_program(source);initial=game.initial();before=copy.deepcopy(initial)
    need(game.outcome(initial)=={'terminal':False,'winners':[]},'Specimen must start nonterminal')
    need(game.intents(initial,case['actor'])==[case['intent']],'Unexpected legal intent set')
    for actor in game.program['players']:
        if actor!=case['actor']:
            need(game.intents(initial,actor)==[],'Wrong actor can act')
            try:game.resolve(initial,actor,case['intent'])
            except IllegalIntent:pass
            else:raise ValueError('Wrong actor was not rejected')
    observed=[]
    for row in game.resolve(initial,case['actor'],case['intent']):
        after=game.reduce(initial,case['actor'],case['intent'],row['event'])
        observed.append({'event':row['event'],'probability':[row['probability'].numerator,row['probability'].denominator],
                         'state':after,'outcome':game.outcome(after)})
        for actor in game.program['players']:
            need(game.observe(after,actor)==after,'Public observation differs')
            need(game.intents(after,actor)==[],'Terminal state has legal intents')
        need(game.reduce(initial,case['actor'],case['intent'],row['event'])==after,'Reduction is not deterministic')
    need(initial==before,'Input state was mutated')
    need(sorted(observed,key=lambda r:canonical(r['event']))==sorted(case['expected'],key=lambda r:canonical(r['event'])),'Observed behavior differs from independent expectations')
    return inspection(game),observed


def build_specimens(root=ROOT):
    directory=root/'tests/fixtures/runtime'
    suite_bytes=(directory/'specimens.json').read_bytes();suite=json.loads(suite_bytes)
    need(suite['purpose']=='developer-fixture' and suite['schemaVersion']=='0.1.0','Unknown specimen suite')
    suite_identity={'id':suite['id'],'version':suite['version'],'sha256':hashlib.sha256(suite_bytes).hexdigest(),
                    'runnerDigest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    outputs={};entries=[]
    for case in suite['cases']:
        need(case['file'] in {'coin.json','weighted-choice.json'},'Undeclared specimen source')
        source_bytes=(directory/case['file']).read_bytes();source=json.loads(source_bytes)
        artifact,observed=verify_case(source,case)
        artifact_set=fingerprint({'sourceBytes':hashlib.sha256(source_bytes).hexdigest(),'implementation':artifact['implementation'],'suite':suite_identity})
        prefix=f'public/data/reference/{artifact_set}/'
        report={'kind':'ReferenceVerification','schemaVersion':'0.1.0','purpose':'developer-fixture',
                'implementation':artifact['implementation'],'subjectDigest':artifact['sourceDigest'],
                'suite':suite_identity,'method':'bounded-exhaustive','result':'pass',
                'scope':'One legal flip from the initial state; every resolved event, resulting observation and terminal outcome.',
                'bounds':{'initialStates':1,'legalIntents':1,'events':len(observed),'terminalStates':len(observed)},
                'sampling':False,'observed':observed}
        raw={'source.json':source_bytes,'inspection.json':canonical(artifact),'verification.json':canonical(report),'suite.json':suite_bytes}
        for name,data in raw.items():outputs[prefix+name]=data
        entries.append({'id':source['id'],'title':case['title'],'source':source,'inspection':artifact,'verification':report,
                        'files':[{'url':'/data/'+(prefix+name).removeprefix('public/data/'),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'label':name} for name,data in raw.items()]})
    index={'schemaVersion':'0.1.0','purpose':'developer-fixture','entries':entries}
    outputs['public/data/reference/catalog.json']=canonical(index)
    return outputs,index


if __name__=='__main__':
    _,index=build_specimens()
    print(json.dumps({'purpose':index['purpose'],'results':[{ 'id':e['id'],'result':e['verification']['result'],'bounds':e['verification']['bounds']} for e in index['entries']]},sort_keys=True))
