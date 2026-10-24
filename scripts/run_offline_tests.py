"""Run every classified offline suite in a fresh Python process, retaining failures."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OFFLINE=(
    'test_browser_search.py','test_browser_network.py','test_fetch_page.py',
    'test_model_vision.py','test_computer_features.py','test_artifacts.py',
    'test_notepad.py','test_notepad_workflow.py','test_workspace_documents.py',
    'test_task_progress.py','test_workspace_io.py','test_reliability.py',
    'test_document_edit.py','test_generated_artifacts.py','test_speech_reference.py',
    'test_model_timing.py','test_efficiency.py','test_prompt_injection.py',
    'test_edge_tools.py','test_popup_windows.py','test_artifact_web_preview.py','test_chat_library.py','test_chat_archives.py','test_document_qa.py',
)
NATIVE={
    'test_artifact_ui.py','test_browser_live.py','test_desktop_live.py',
    'test_efficiency_ui.py','test_notepad_live.py','test_progress_ui.py',
    'test_speech_ui.py','test_vision_ui.py','test_workspace_io_live.py','test_workspace_live.py',
    'test_edge_live.py','test_popup_ui.py','test_artifact_web_live.py','test_chat_library_ui.py','test_document_qa_ui.py',
}

def main():
    if not __debug__:raise RuntimeError('Plain asserts require Python without -O')
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'test-results')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    actual={p.name for p in ROOT.glob('test_*.py')}
    if actual!=set(OFFLINE)|NATIVE:
        raise RuntimeError('Classify added/removed test suites explicitly: '+str(actual^(set(OFFLINE)|NATIVE)))
    env=os.environ.copy()
    env.update(PYTHONPATH=str(ROOT/'scripts/ci_guard'),PYTHONIOENCODING='utf-8',
               HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    probe=subprocess.run([sys.executable,'-B','-c',
        "import socket; socket.getaddrinfo('offline-tripwire.invalid',443)"],
        cwd=ROOT,env=env,capture_output=True,text=True)
    if probe.returncode==0 or 'Offline CI refused' not in probe.stderr:
        raise RuntimeError('The socket audit tripwire is not active')
    rows=[]
    for suite in OFFLINE:
        start=time.perf_counter();command=[sys.executable,'-B',suite]
        if suite=='test_prompt_injection.py':
            command+=['--report',str(output/'prompt-injection.json')]
        try:
            result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
            row=dict(suite=suite,returncode=result.returncode,seconds=round(time.perf_counter()-start,4))
            (output/(suite+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        except subprocess.TimeoutExpired:
            row=dict(suite=suite,returncode=-1,seconds=60,error='60-second suite deadline exceeded')
        rows.append(row);print(('PASS ' if row['returncode']==0 else 'FAIL ')+suite,flush=True)
        (output/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(f"{sum(r['returncode']==0 for r in rows)}/{len(rows)} offline suites passed.")
    return int(any(r['returncode']!=0 for r in rows))

if __name__=='__main__':raise SystemExit(main())
