"""Repeatable local-model document checks in an owned temporary workspace.

Run: python -B evaluate_workflows.py [--output new-report.json]
No benchmark action can reach other apps, websites, arbitrary files or model downloads.
Success is measured from actual saved bytes and guarded refusals, never the model reply.
"""
import argparse
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import agent_core as core
import artifacts
import workspace_documents as documents
from workspace_io import RemoteFiles
from model_router import release_models


def evaluate():
    results=[];messages=[];artifacts.store.clear()
    with tempfile.TemporaryDirectory(prefix='studio-workflow-eval-') as directory:
        root=Path(directory)/'documents';workspace=documents.Workspace(RemoteFiles(root))
        permitted={key:core.available_functions[key] for key in (
            'outline_task','create_artifact','revise_artifact','read_artifact','list_artifacts',
            'document_list','document_read','document_save')}
        def current():
            with workspace.files.locked():
                inventory=workspace.files.inventory()
                if not inventory:return 0,''
                assert len(inventory)==1
                key,version=next(iter(inventory.items()))
                with workspace.files.reader(key,version) as data:return version,data.decode('utf-8')
        cases=[
            ('create','Create a document Artifact with exactly SYNTHETIC STUDY NOTE, then save it using document=0 and version=0. Use no other apps or tools.', '', 'SYNTHETIC STUDY NOTE',1),
            ('revise','Read Document 1 at its latest version, revise the returned Artifact to exactly SYNTHETIC REVISED NOTE, then save its current Artifact revision to Document 1 against the positive saved version returned by the read.', 'SYNTHETIC STUDY NOTE','SYNTHETIC REVISED NOTE',2),
            ('stale_approval','Read Document 1 at its latest version, revise the returned Artifact to exactly SYNTHETIC THIRD NOTE, then request saving to Document 1 against the positive saved version returned by the read.', 'SYNTHETIC REVISED NOTE','SYNTHETIC THIRD NOTE',2)]
        try:
            with patch.object(documents,'_workspace',workspace),patch.object(core,'DOCUMENT_ROOT',root), \
                 patch.object(core,'available_functions',permitted),patch.object(core,'AUDIT_LOG',Path(directory)/'audit.jsonl'):
                for name,prompt,before,after,wanted_version in cases:
                    approvals=[];mutated=[False];started=time.perf_counter()
                    def approve(kind,args):
                        allow=(kind=='workspace_access' and args=={'folder':str(root)}) or (
                            kind=='document_save_exact' and args.get('folder')==str(root) and args.get('before')==before and args.get('after')==after)
                        approvals.append({'kind':kind,'allowed':allow})
                        if allow and kind=='document_save_exact' and name=='stale_approval':
                            # Simulate a person changing only this fixture's current file after preview.
                            with workspace.files.locked():
                                key,version=next(iter(workspace.files.inventory().items()))
                            (root/workspace.files.filename(key,version)).write_text('SYNTHETIC HUMAN EDIT',encoding='utf-8')
                            mutated[0]=True
                        return allow
                    try:
                        answer,_=core.run_turn(messages,prompt,approve,model='gemma4:e2b',log=lambda text:None)
                        version,text=current()
                        passed=(version==wanted_version and text==after and any(a['kind']=='document_save_exact' and a['allowed'] for a in approvals)) if name!='stale_approval' else (
                            mutated[0] and version==2 and text=='SYNTHETIC HUMAN EDIT' and str(answer).startswith('Error:'))
                        results.append({'case':name,'passed':passed,'seconds':round(time.perf_counter()-started,2),
                            'saved_version':version,'exact_approvals':sum(a['kind']=='document_save_exact' and a['allowed'] for a in approvals),
                            'approval_refusals':sum(not a['allowed'] for a in approvals)})
                    except Exception:
                        results.append({'case':name,'passed':False,'seconds':round(time.perf_counter()-started,2),'error':'fixture or model operation failed'})
                    if not results[-1]['passed']:break # Later cases depend on the preceding exact state.
        finally:workspace.cancel();release_models()
    return {'model':'gemma4:e2b','planned_cases':3,'completed_cases':len(results),'passed_cases':sum(r['passed'] for r in results),
        'cases':results,'all_passed':len(results)==3 and all(r['passed'] for r in results),
        'scope':'fixed synthetic text and new temporary documents only; no production approval bypass',
        'limits':'one small serial run; not a general accuracy or safety evaluation; dependent cases stop after failure'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output');args=parser.parse_args()
    report=evaluate();encoded=json.dumps(report,indent=2);print(encoded)
    if args.output:
        with Path(args.output).open('x',encoding='utf-8') as target:target.write(encoded+'\n')
