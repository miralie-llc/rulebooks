"""Review public changes against an exact Git base; never infer editorial acceptance."""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.check_repository import snapshot, inventory, commit_id
from tools.prepublish import prepublish
from tools.runtime.engine import canonical, compile_program, fingerprint, inspection

ROOT=Path(__file__).resolve().parents[1]


def records(files):
    result={}
    for path,raw in files.items():
        if path.startswith('data/') and path.endswith('.json'):
            value=json.loads(raw)
            if isinstance(value,dict) and value.get('kind') in {'Game','GameFamily','PublisherEdition','RulebookEdition','Source','Concept','BGSMRelease','Formalization','VerificationRecord','DefinitionPackage','BuildArtifact'}:
                key=(value['kind'],value.get('id',value.get('version')),value.get('revision'))
                if key in result:raise ValueError('Duplicate record identity in review inputs')
                result[key]=(path,value)
    return result


def rows(before,after):
    return [{'id':key,'before':before.get(key),'after':after.get(key)} for key in sorted(set(before)|set(after)) if before.get(key)!=after.get(key)]


def record_diff(before_files,after_files):
    before,after=records(before_files),records(after_files);changes=[]
    for key in sorted(set(before)|set(after)):
        old=before.get(key);new=after.get(key)
        if old and new and old[1]==new[1]:continue
        item={'kind':key[0],'id':key[1],'revision':key[2],'change':'changed' if old and new else 'added' if new else 'removed',
              'beforeDigest':fingerprint(old[1]) if old else None,'afterDigest':fingerprint(new[1]) if new else None,
              'path':(new or old)[0]}
        if key[0]=='RulebookEdition':
            def rules(value):return {r['id']:r for section in value['sections'] for r in section['rules']} if value else {}
            item['rules']=rows(rules(old[1] if old else None),rules(new[1] if new else None))
            item['metadataChanged']=[field for field in ('label','scope','dimensions','readingStatus','origin','sections') if (old[1].get(field) if old else None)!=(new[1].get(field) if new else None)]
        if key[0]=='Formalization':
            item['coverage']=rows({r['rule']:r for r in old[1]['coverage']} if old else {},{r['rule']:r for r in new[1]['coverage']} if new else {})
        if key[0] not in {'RulebookEdition','Formalization'}:
            item['fields']=rows(old[1] if old else {},new[1] if new else {})
        changes.append(item)
    return changes


def behavior(source,limit=128):
    game=compile_program(source);queue=deque([game.initial()]);states={};transitions=0
    while queue:
        state=queue.popleft();key=canonical(state).decode()
        if key in states:continue
        if len(states)>=limit:return {'complete':False,'states':states,'transitions':transitions,'reason':'State exploration limit reached'}
        row={'outcome':game.outcome(state),'actors':{}}
        for actor in game.program['players']:
            actor_row={'observation':game.observe(state,actor),'intents':[]}
            for intent in game.intents(state,actor):
                alternatives=[]
                for resolution in game.resolve(state,actor,intent):
                    transitions+=1
                    if transitions>4096:return {'complete':False,'states':states,'transitions':transitions,'reason':'Transition exploration limit reached'}
                    after=game.reduce(state,actor,intent,resolution['event']);queue.append(after)
                    probability=resolution['probability']
                    alternatives.append({'event':resolution['event'],'state':after,'probability':[probability.numerator,probability.denominator]})
                actor_row['intents'].append({'intent':intent,'alternatives':alternatives})
            row['actors'][actor]=actor_row
        states[key]=row
    return {'complete':True,'states':states,'transitions':transitions}


def definition_diffs(before,after):
    changes=[]
    names={p for p in set(before)|set(after) if p.startswith('data/definitions/') and p.endswith('.json')}
    for name in sorted(names):
        if before.get(name)==after.get(name):continue
        item={'path':name,'comparison':'Both sources evaluated by the current pinned reference implementation; historical runtime equivalence is not implied.'}
        traces={}
        for label,files in [('before',before),('after',after)]:
            if name not in files:item[label]={'present':False};continue
            try:
                source=json.loads(files[name]);trace=behavior(source);traces[label]=trace
                item[label]={'present':True,'sourceDigest':fingerprint(source),'implementation':inspection(compile_program(source))['implementation'],
                             'complete':trace['complete'],'states':len(trace['states']),'transitions':trace['transitions']}
                if not trace['complete']:item[label]['reason']=trace['reason']
            except (ValueError,TypeError,KeyError,RecursionError):item[label]={'present':True,'complete':False,'error':'Unsupported or invalid source; inspect locally'}
        if len(traces)==2:
            different=rows(traces['before']['states'],traces['after']['states'])
            item['changedStates']=len(different)
            item['behaviorEquivalentWithinExploredBounds']=not different and all(t['complete'] for t in traces.values())
        changes.append(item)
    return changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/review/editorial.json')
    args=parser.parse_args()
    try:
        output=args.output.resolve()
        if not output.is_relative_to((ROOT/'.cache/review').resolve()):raise ValueError('Review reports must remain in .cache/review')
        review=prepublish(ROOT,candidate='working',base=args.base)
        if review['status']!='passed':raise ValueError('Credential review failed')
        before=snapshot(ROOT,'head',args.base);after=snapshot(ROOT,'working')
        if inventory(after)!=review['snapshot']:raise ValueError('Candidate changed during review')
        result={'schemaVersion':'0.1.0','baseCommit':commit_id(ROOT,args.base),'headCommit':review['head'],'candidateMode':'working','candidateDigest':review['snapshot']['sha256'],
                'acceptance':'pending','records':record_diff(before,after),'behavior':definition_diffs(before,after),
                'withdrawalPolicy':'Publication assembler rejects withdrawals until an explicit removal policy is implemented.'}
        output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(canonical(result));output.chmod(0o600)
        print(json.dumps({'changedRecords':len(result['records']),'changedDefinitions':len(result['behavior']),'candidateDigest':result['candidateDigest'],'acceptance':'pending'}))
    except (ValueError,OSError):
        if 'output' in locals() and output.is_relative_to((ROOT/'.cache/review').resolve()):
            output.unlink(missing_ok=True)
        parser.exit(1,'Editorial diff failed; inspect the candidate and local checks. No acceptance or publication occurred.\n')


if __name__=='__main__':main()
