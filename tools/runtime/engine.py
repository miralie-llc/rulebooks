"""Finite, pure reference evaluator. Expressions never execute Python or load plugins."""
import copy
from fractions import Fraction
import hashlib
from itertools import product
import json
import platform
from importlib.metadata import version as package_version
from pathlib import Path
import re
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[2]
IMPLEMENTATION={'id':'rulebooks-reference','version':'0.1.0'}
SCHEMA=ROOT/'schema/runtime/0.1.0/program.schema.json'
LIMIT=1_000_000_000
ARITY={'eq':2,'lt':2,'le':2,'add':2,'sub':2,'and':2,'or':2,'not':1,'if':3,'get':2,'set':3,'sum':1,'length':1,'array':None,'object':None}


class ProgramError(ValueError):pass
class IllegalIntent(ProgramError):pass


def need(condition,message):
    if not condition:raise ProgramError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def fingerprint(value):return hashlib.sha256(canonical(value)).hexdigest()


def json_value(value,depth=0):
    need(depth<=24,'Value nesting limit exceeded')
    if value is None or type(value) is bool:return
    if type(value) is int:need(abs(value)<=LIMIT,'Integer limit exceeded');return
    if type(value) is str:need(len(value)<=1024,'String limit exceeded');return
    if type(value) is list:
        need(len(value)<=128,'List limit exceeded')
        for child in value:json_value(child,depth+1)
        return
    if type(value) is dict:
        need(len(value)<=32 and all(type(k) is str for k in value),'Object limit exceeded')
        for child in value.values():json_value(child,depth+1)
        return
    raise ProgramError('Only bounded JSON values and integers are supported')


def expression(node,roots,slots,parameters,depth=0):
    need(depth<=24,'Expression nesting limit exceeded')
    if not isinstance(node,dict):json_value(node);return
    if set(node)=={'literal'}:json_value(node['literal']);return
    if set(node)=={'var'}:
        need(isinstance(node['var'],str),'Invalid variable')
        parts=node['var'].split('.')
        need(len(parts)<=3 and all(re.fullmatch(r'[a-z][a-zA-Z0-9]*',p) for p in parts),'Invalid variable path')
        need(parts[0] in roots,'Variable unavailable in this phase')
        if parts[0]=='state' and len(parts)>1:need(parts[1] in slots,'Unknown state slot')
        if parts[0]=='params' and len(parts)>1:need(parts[1] in parameters,'Unknown action parameter')
        return
    need(set(node)=={'op','args'} and node['op'] in ARITY and isinstance(node['args'],list),'Unknown expression operation or shape')
    op,args=node['op'],node['args']
    need(len(args)<=128 and (ARITY[op] is None or len(args)==ARITY[op]),'Wrong operation arity')
    if op=='object':
        need(all(isinstance(pair,list) and len(pair)==2 and isinstance(pair[0],str) for pair in args),'Object expects key/expression pairs')
        need(len({pair[0] for pair in args})==len(args),'Duplicate object key')
        for _,value in args:expression(value,roots,slots,parameters,depth+1)
    else:
        for value in args:expression(value,roots,slots,parameters,depth+1)


def compile_program(source):
    need(type(source) is dict,'Program must be an object')
    need(len(canonical(source))<=65536,'Program exceeds 64 KiB')
    need(not list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(source)),'Program violates the versioned shape or exact version pins')
    program=json.loads(canonical(source))
    json_value(program['initial'])
    required={'finite-intents','public-state','deterministic-reduction'}
    need(required<=set(program['capabilities']),'Missing required capability declarations')
    need(len({a['id'] for a in program['actions']})==len(program['actions']),'Duplicate action ID')
    slots=set(program['initial']);total=0;has_chance=False
    for action in program['actions']:
        parameters=action['parameters'];count=1
        for values in parameters.values():
            for value in values:json_value(value)
            count*=len(values)
        total+=count;need(total<=4096,'Finite intent enumeration exceeds 4096 candidates')
        expression(action['legal'],{'state','actor','params'},slots,parameters)
        resolution=action['resolve']
        if isinstance(resolution,dict) and 'chance' in resolution:
            has_chance=True
            need(set(resolution)=={'chance'} and isinstance(resolution['chance'],list) and 1<=len(resolution['chance'])<=64,'Invalid chance alternatives')
            for branch in resolution['chance']:
                need(isinstance(branch,dict) and set(branch)=={'weight','value'},'Invalid chance branch')
                need(type(branch['weight']) is int and 0<branch['weight']<=LIMIT,'Chance weights must be positive bounded integers')
                expression(branch['value'],{'state','actor','params'},slots,parameters)
        else:expression(resolution,{'state','actor','params'},slots,parameters)
        need(set(action['effects'])<=slots,'Effects cannot introduce undeclared state slots')
        for value in action['effects'].values():expression(value,{'state','event'},slots,{})
    need(not has_chance or 'exact-chance' in program['capabilities'],'Chance requires explicit capability')
    expression(program['outcome'],{'state'},slots,{})
    for link in program['sourceMap']:
        value=program
        try:
            for part in link['node'].split('/')[1:]:
                part=part.replace('~1','/').replace('~0','~')
                if isinstance(value,list):
                    need(re.fullmatch(r'0|[1-9][0-9]*',part) is not None,'Noncanonical array source pointer')
                    value=value[int(part)]
                else:value=value[part]
        except (KeyError,IndexError,ValueError,TypeError):raise ProgramError('Source map points to a missing node') from None
    # Evaluate initialization/outcome now; state-dependent typing is checked at runtime.
    game=Game(program)
    game.outcome(program['initial'])
    return game


def integer(value):need(type(value) is int,'Expected integer');return value

def boolean(value):need(type(value) is bool,'Expected boolean');return value


def evaluate(node,env):
    if not isinstance(node,dict):return copy.deepcopy(node)
    if 'literal' in node:return copy.deepcopy(node['literal'])
    if 'var' in node:
        value=env
        for key in node['var'].split('.'):
            need(isinstance(value,dict) and key in value,'Unavailable variable value')
            value=value[key]
        return copy.deepcopy(value)
    op,args=node['op'],node['args']
    ev=lambda value:evaluate(value,env)
    if op=='if':return ev(args[1] if boolean(ev(args[0])) else args[2])
    if op=='and':return boolean(ev(args[0])) and boolean(ev(args[1]))
    if op=='or':return boolean(ev(args[0])) or boolean(ev(args[1]))
    if op=='object':return {key:ev(value) for key,value in args}
    values=[ev(value) for value in args]
    if op=='array':result=values
    elif op=='eq':result=canonical(values[0])==canonical(values[1])
    elif op=='not':result=not boolean(values[0])
    elif op in {'lt','le','add','sub'}:
        left,right=map(integer,values)
        result={'lt':lambda:left<right,'le':lambda:left<=right,'add':lambda:left+right,'sub':lambda:left-right}[op]()
    elif op in {'get','set'}:
        sequence,index=values[:2];need(isinstance(sequence,list),'Expected list');integer(index)
        need(0<=index<len(sequence),'List index out of bounds')
        if op=='get':result=sequence[index]
        else:result=copy.deepcopy(sequence);result[index]=values[2]
    elif op in {'length','sum'}:
        need(isinstance(values[0],list),'Expected list')
        result=len(values[0]) if op=='length' else sum(integer(value) for value in values[0])
    else:raise ProgramError('Unsupported operation')
    json_value(result)
    return result


class Game:
    def __init__(self,program):self._program=copy.deepcopy(program)
    @property
    def program(self):return copy.deepcopy(self._program)
    def initial(self):return copy.deepcopy(self._program['initial'])
    def state(self,value):
        json_value(value)
        need(isinstance(value,dict) and set(value)==set(self._program['initial']),'State must contain exactly the declared slots')
    def observe(self,state,actor):
        self.state(state);need(actor in self._program['players'],'Unknown player')
        return copy.deepcopy(state)  # This version supports public information only.
    def outcome(self,state):
        self.state(state);value=evaluate(self._program['outcome'],{'state':state})
        need(isinstance(value,dict) and set(value)=={'terminal','winners'},'Outcome must identify terminal and winners')
        boolean(value['terminal']);need(isinstance(value['winners'],list),'Winners must be a list')
        need(all(p in self._program['players'] for p in value['winners']) and len(set(value['winners']))==len(value['winners']),'Invalid winners')
        need(value['terminal'] or not value['winners'],'Nonterminal state cannot have winners')
        return value
    def legal(self,state,actor,intent):
        self.state(state)
        if actor not in self._program['players'] or self.outcome(state)['terminal']:return False
        if not isinstance(intent,dict) or set(intent)!={'action','params'}:return False
        action=next((a for a in self._program['actions'] if a['id']==intent['action']),None)
        if not action or not isinstance(intent['params'],dict) or set(intent['params'])!=set(action['parameters']):return False
        if any(not any(canonical(v)==canonical(intent['params'][k]) for v in values) for k,values in action['parameters'].items()):return False
        return boolean(evaluate(action['legal'],{'state':state,'actor':actor,'params':intent['params']}))
    def intents(self,state,actor):
        self.state(state);result=[]
        for action in self._program['actions']:
            keys=list(action['parameters'])
            for values in product(*(action['parameters'][k] for k in keys)):
                intent={'action':action['id'],'params':dict(zip(keys,values))}
                if self.legal(state,actor,intent):result.append(intent)
        return result
    def resolve(self,state,actor,intent):
        if not self.legal(state,actor,intent):raise IllegalIntent('Intent rejected without state mutation')
        action=next(a for a in self._program['actions'] if a['id']==intent['action'])
        resolution=action['resolve'];env={'state':state,'actor':actor,'params':intent['params']}
        branches=resolution['chance'] if isinstance(resolution,dict) and 'chance' in resolution else [{'weight':1,'value':resolution}]
        total=sum(b['weight'] for b in branches);merged={}
        for branch in branches:
            event=evaluate(branch['value'],env);json_value(event);key=canonical(event)
            probability=Fraction(branch['weight'],total)
            if key in merged:merged[key]['probability']+=probability
            else:merged[key]={'event':event,'probability':probability}
        return [merged[key] for key in sorted(merged)]
    def reduce(self,state,actor,intent,event):
        need(any(canonical(row['event'])==canonical(event) for row in self.resolve(state,actor,intent)),'Event is not an allowed resolution of this intent')
        action=next(a for a in self._program['actions'] if a['id']==intent['action'])
        # Every effect reads the same pre-state. Apply once, without mutating the input.
        updates={key:evaluate(value,{'state':state,'event':event}) for key,value in action['effects'].items()}
        result=copy.deepcopy(state);result.update(updates);self.outcome(result)
        return result


def inspection(game):
    files=[Path(__file__),SCHEMA,ROOT/'tools/requirements-ci.txt']
    identity={'files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'python':platform.python_version(),'jsonschema':package_version('jsonschema')}
    build=fingerprint(identity)
    return {'kind':'ReferenceInspection','schemaVersion':'0.1.0','status':'experimental',
            'implementation':{**IMPLEMENTATION,'buildDigest':build},'sourceDigest':fingerprint(game.program),
            'build':identity,'program':game.program,'sourceMap':game.program['sourceMap']}
