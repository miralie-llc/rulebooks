"""Explicit, digest-pinned projections of evidenced semantic work; empty is valid."""
import json
from tools.assemble_publication import sha
from tools.validate_publication import require
from tools.validate_work import validate_records


def selected_gaps(root,content):
    selection=json.loads((root/'data/site/gaps.json').read_text())
    require(set(selection)=={'schemaVersion','items'} and selection['schemaVersion']=='0.1.0' and isinstance(selection['items'],list),'Invalid public gap selection')
    work=[(path,json.loads(path.read_text())) for path in sorted((root/'work').glob('*/*.json'))]
    validate_records(work,root=root)
    by_id={value['id']:(path,value) for path,value in work}
    selected=[];seen=set()
    for pin in selection['items']:
        require(set(pin)=={'id','sha256'} and pin['id'] not in seen,'Gap selection requires unique exact pins')
        seen.add(pin['id']);require(pin['id'] in by_id,'Selected gap is missing')
        path,item=by_id[pin['id']]
        require(sha(path.read_bytes())==pin['sha256'],'Selected gap changed; review and repin')
        require(item['queue']=='semantic' and item['kind']=='semantic-gap' and item['status'] in {'review','done'},'Only reviewed-for-selection or completed evidenced gaps can appear')
        target=item['target']
        require(target['kind']=='rulebook','Published gap needs an exact rulebook target')
        editions=[r for r in content['records'] if r['kind']=='RulebookEdition' and r['id']==target['id'] and str(r['revision'])==target.get('revision') and not r.get('testOnly')]
        require(len(editions)==1,'Gap target must be an actual selected rulebook record')
        require(item.get('evidence'),'Gap needs evidence')
        # At least one local evidence record must identify the actual rulebook.
        matched=False
        for evidence in item['evidence']:
            file=root/evidence['path']
            if file.suffix=='.json':
                value=json.loads(file.read_text())
                if value==editions[0]:matched=True
        require(matched,'Gap evidence must include the exact target rulebook data')
        selected.append({key:item[key] for key in ('id','title','status','target','gap','evidence') } | {'sha256':pin['sha256']})
    return {'schemaVersion':'0.1.0','purpose':'selected-product-work','items':selected}
