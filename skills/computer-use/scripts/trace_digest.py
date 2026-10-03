"""Index NDJSON observations and outcomes without treating trace text as instructions."""
import argparse
import hashlib
import json
import os
from pathlib import Path

KINDS={'observation','action','verification','decision','handoff'}


def digest(raw,group_size=20):
    if isinstance(group_size,bool) or not isinstance(group_size,int) or group_size<1:
        raise ValueError('group_size must be a positive integer.')
    events=[];seen=set()
    for line_number,line in enumerate(raw.decode('utf-8').splitlines(),1):
        if not line.strip():continue
        event=json.loads(line)
        if not isinstance(event,dict):raise ValueError(f'Line {line_number} is not an event object.')
        identity=event.get('id')
        if not isinstance(identity,str) or not identity.strip() or identity in seen:
            raise ValueError(f'Line {line_number} has a missing or repeated event id.')
        if event.get('kind') not in KINDS:raise ValueError(f'Line {line_number} has an unknown kind.')
        for key in ['status','summary']:
            if not isinstance(event.get(key),str) or not event[key].strip():
                raise ValueError(f'Line {line_number} needs a nonempty {key}.')
        refs=event.get('evidence_refs',[])
        if not isinstance(refs,list) or not all(isinstance(ref,str) and ref.strip() for ref in refs):
            raise ValueError(f'Line {line_number} has invalid evidence_refs.')
        risk=event.get('risk','normal')
        if not isinstance(risk,str) or not risk.strip():raise ValueError(f'Line {line_number} has invalid risk.')
        seen.add(identity)
        context={}
        for key in ['step','source']:
            if key in event:
                if not isinstance(event[key],str) or not event[key].strip():
                    raise ValueError(f'Line {line_number} has invalid {key}.')
                context[key]=event[key]
        events.append({**context,'id':identity,'line':line_number,'kind':event['kind'],'status':event['status'],
                       'summary':event['summary'][:280],'summary_truncated':len(event['summary'])>280,
                       'risk':risk,'evidence_refs':refs})
    groups=[]
    for start in range(0,len(events),group_size):
        part=events[start:start+group_size]
        groups.append({'start_line':part[0]['line'],'end_line':part[-1]['line'],
                       'event_ids':[e['id'] for e in part], 'first_report':part[0], 'last_report':part[-1]})
    attention=[e for e in events if e['risk']!='normal' or e['status'] not in {'passed','observed','executed'}
               or e['kind'] in {'decision','handoff'}]
    return {'trust':'untrusted_trace_data','authorizes_actions':False,'validates_business_outcomes':False,
            'raw_sha256':hashlib.sha256(raw).hexdigest(),'event_count':len(events),
            'groups':groups,'attention':attention}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace',type=Path)
    parser.add_argument('--group-size',type=int,default=20)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=digest(args.trace.read_bytes(),args.group_size)
        result['raw_ref']=str(args.trace)
        descriptor=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            stream.write(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    except (ValueError,OSError) as err:parser.error(str(err))
    print(json.dumps({'indexed':result['event_count'],'attention_count':len(result['attention']),
                      'output':str(args.output)},ensure_ascii=False))


if __name__=='__main__':main()
