"""Small public discovery projections and verified download inventory."""
from collections import Counter
from tools.assemble_publication import canonical, sha, record_path
from tools.validate_publication import require

GAME_BUDGET = 20 * 1024


def indexes(content, outputs):
    by_key={(r['kind'],r.get('id'),r.get('revision')):r for r in content['records']}
    entries=[];discovery={};sizes={}
    mode=content['mode']
    for pin in content['games']:
        game=by_key['Game',pin['id'],pin['revision']]
        edition=by_key['RulebookEdition',game['defaultEdition']['id'],game['defaultEdition']['revision']]
        mappings=[r for r in content['records'] if r['kind']=='Formalization' and r['edition']==game['defaultEdition']]
        row={'schemaVersion':'0.1.0','mode':mode,'game':pin,'title':game['title'],
             'url':'/games/'+game['id']+'/', 'rulebook':game['defaultEdition'],
             'scope':edition['scope']['summary'],'reading':edition['readingStatus'],
             'record':'/data/'+record_path(game),'rulebookRecord':'/data/'+record_path(edition),
             'formalizations':[{'id':m['id'],'revision':m['revision'],'coverage':dict(sorted(Counter(c['status'] for c in m['coverage']).items()))} for m in mappings]}
        for field in ('family','publisherEdition','tags','aliases'):
            if field in game:row[field]=game[field]
        raw=canonical(row);require(len(raw)<=GAME_BUDGET,'Game discovery JSON exceeds 20 KiB; split expanded data')
        name='public/data/discovery/games/'+game['id']+'.json';discovery[name]=raw;sizes[game['id']]=len(raw)
        entries.append({'kind':'game','title':game['title'],'url':row['url'],'status':'reviewed' if mode=='publication' else mode,
                        'text':' '.join([game['title'],*game.get('aliases',[]),*game.get('tags',[]),row['scope']])})
    for release in (r for r in content['records'] if r['kind']=='BGSMRelease'):
        for pin in release['concepts']:
            concept=by_key['Concept',pin['id'],pin['revision']]
            entries.append({'kind':'concept','title':concept['title'],'url':f"/bgsm/{release['version']}/concepts/{concept['id']}/",
                            'status':release['status'],'version':release['version'],'text':concept['title']+' '+concept['meaning']})
    vocabulary=content['vocabulary']
    for term in vocabulary['terms']:
        entries.append({'kind':'vocabulary','title':term['title'],'url':f"/vocabulary/{vocabulary['version']}/#term-{term['id']}",
                        'status':'editorial-draft','text':term['title']+' '+term['meaning']})
    search={'schemaVersion':'0.1.0','mode':mode,'entries':entries}
    discovery['public/data/search.json']=canonical(search)
    budget={'limitBytes':GAME_BUDGET,'games':sizes,'maxBytes':max(sizes.values(),default=0)}
    discovery['public/data/discovery/budget.json']=canonical(budget)
    # Hash the actual served bytes, including assembler receipts, manifests and assets.
    files=[{'url':'/data/'+name.removeprefix('public/data/'),'sha256':sha(raw),'bytes':len(raw)}
           for name,raw in sorted({**outputs,**discovery}.items()) if name.startswith('public/data/')]
    downloads={'schemaVersion':'0.1.0','mode':mode,'files':files}
    discovery['public/data/downloads.json']=canonical(downloads)
    return discovery,search,downloads,budget
