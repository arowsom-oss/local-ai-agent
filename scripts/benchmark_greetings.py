"""Paired synthetic full-turn timings. No tool action or private conversation is used."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert not args.output.exists(),'Retain prior evidence'
sys.path.insert(0,str(args.repo.resolve()))
import agent_core as core
import model_router as router

rows=[]
def trial(mode,warmup=False):
    logs=[];messages=[];tool_attempts=[]
    def refuse(name,values):
        tool_attempts.append(name)
        return 'benchmark refuses all actions'
    started=time.perf_counter()
    with patch.object(core,'audit'),patch.object(core,'tool_args_problem',side_effect=refuse):
        answer,reported=core.run_turn(messages,'hi',lambda *a:False,model=mode,log=logs.append)
    wall=time.perf_counter()-started
    metrics=[json.loads(line[len('[timing] '):]) for line in logs if line.startswith('[timing] ')]
    row=dict(mode=mode,warmup=warmup,wall_seconds=wall,reported_seconds=reported,
             nonempty_reply=isinstance(answer,str) and bool(answer.strip()),
             reply_error=not isinstance(answer,str) or answer.startswith(('Error:','(stopped:')),
             reply_characters=len(answer or ''),tool_attempts=tool_attempts,
             metrics=metrics,routes=[line for line in logs if line.startswith('[route] ')])
    rows.append(row)
    report=dict(prompt='hi (fixed public synthetic greeting)',rows=rows,
                scope='Same full system prompt and tool schemas. Every action refused. No reply/reasoning payload persisted.')
    usable=[r for r in rows if not r['warmup']]
    report['median_wall_seconds']={mode:statistics.median(r['wall_seconds'] for r in usable if r['mode']==mode)
                                  for mode in ('auto',router.FAST_MODEL) if any(r['mode']==mode for r in usable)}
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(mode=mode,warmup=warmup,seconds=round(wall,4),calls=len(metrics),
                         tool_attempts=tool_attempts,reply_error=row['reply_error'])),flush=True)
    assert not row['reply_error'] and row['nonempty_reply'] and not tool_attempts

trial(router.FAST_MODEL,warmup=True)
for pair in range(6):
    modes=('auto',router.FAST_MODEL) if pair%2==0 else (router.FAST_MODEL,'auto')
    for mode in modes:trial(mode)
