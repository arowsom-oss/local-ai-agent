"""Native Tk/codec efficiency regressions using only synthetic local media.

Use --measure-only --report PATH for an unmodified historical comparison.
No microphone, inference, browser, personal files or Internet are used.
"""
import argparse
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
from unittest.mock import patch

import av
from PIL import Image
import artifact_panel
from artifacts import store
import chat_window as ui


def run():
    ui.build_window()
    ui.root.title('Local Studio - synthetic efficiency fixture')
    ui.root.geometry('1280x800')
    panel=ui.artifact_panel; errors=[]; calls=[]; guard=threading.Lock()
    ui.root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
    original=artifact_panel.prepare_preview

    def tracked(kind,data,stop):
        started=time.perf_counter()
        with guard:
            item={'kind':kind,'finished':False}; calls.append(item)
            item['concurrent']=sum(not c['finished'] for c in calls)
        try:return original(kind,data,stop)
        finally:
            with guard:item.update(finished=True,seconds=round(time.perf_counter()-started,4))

    def pump(test, timeout=20):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            ui.root.update()
            if test():return
            time.sleep(.01)
        raise AssertionError('Native efficiency fixture timed out')

    def wait_idle():
        pump(lambda:bool(calls) and all(c['finished'] for c in calls)
             and panel.mail.empty() and bool(panel.frames))
        until=time.monotonic()+.35
        while time.monotonic()<until:ui.root.update();time.sleep(.01)
        pump(lambda:all(c['finished'] for c in calls) and panel.mail.empty())

    def article():
        item=store.create('Synthetic article','document','Original human article.')
        panel.load(item.number);panel.refresh();ui.root.update();return item

    result={}
    try:
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'synthetic.jpg'
            Image.new('RGB',(384,256),'navy').save(photo)
            video=Path(folder)/'synthetic.mp4'
            with av.open(str(video),'w') as container:
                stream=container.add_stream('libx264',rate=24)
                stream.width,stream.height,stream.pix_fmt=384,256,'yuv420p'
                for index in range(65):
                    frame=av.VideoFrame.from_image(Image.new('RGB',(384,256),(index*3,40,90)))
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            with patch.object(artifact_panel,'prepare_preview',side_effect=tracked):
                for kind,path,count in (('image',photo,1),('video',video,65)):
                    article(); calls.clear(); started=time.perf_counter()
                    with patch.object(artifact_panel.filedialog,'askopenfilename',return_value=str(path)):
                        panel.import_file()
                    pump(lambda:panel.selected.kind==kind and len(panel.frames)==count)
                    first_visible=time.perf_counter()-started
                    wait_idle()
                    result[kind]=dict(decode_jobs=len(calls),max_concurrent=max(c['concurrent'] for c in calls),
                                      first_visible_s=round(first_visible,4),calls=[dict(c) for c in calls],
                                      frames=len(panel.frames))
            result['one_decode_per_import']=all(result[k]['decode_jobs']==1 for k in ('image','video'))

            # Pause/resume without pumping Tk between clicks must leave one timer.
            panel.frames=[(0.0,None),(.5,None),(1.0,None)]
            with patch.object(panel,'show_frame'):
                before=set(ui.root.tk.call('after','info'))
                for _ in range(3):panel.toggle_play()
                after=set(ui.root.tk.call('after','info'))
                result['playback_timers_after_rapid_resume']=len(after-before)
                panel.toggle_play()
            panel.reset();store.clear();ui.root.update()

            item=article(); gate=threading.Event(); begun=threading.Event(); calls.clear()
            def gated(kind,data,stop):begun.set();gate.wait(3);return tracked(kind,data,stop)
            with patch.object(artifact_panel,'prepare_preview',side_effect=gated), \
                    patch.object(artifact_panel.filedialog,'askopenfilename',return_value=str(photo)):
                panel.import_file()
                pump(begun.is_set)
                panel.editor.insert('end','\nNew unsaved human addition.')
                ui.root.update();gate.set()
                pump(lambda:any(a.title=='Imported image' for a in store.items()))
                pump(lambda:all(c['finished'] for c in calls) and panel.mail.empty())
                result['concurrent_human_edit_preserved']=(panel.selected.number==item.number and panel.dirty
                    and panel.editor.get('1.0','end-1c').endswith('New unsaved human addition.'))
            panel.reset();store.clear();ui.root.update()

            # An obsolete preview must stop independently of global Stop.
            started=threading.Event(); cancelled=threading.Event(); release=threading.Event()
            def slow(kind,data,stop):
                started.set()
                deadline=time.monotonic()+2
                while time.monotonic()<deadline and not release.wait(.01):
                    if stop.is_set():cancelled.set();break
                raise ValueError('Synthetic cancelled preview')
            image=store.media('Synthetic delayed preview','image',photo.read_bytes())
            with patch.object(artifact_panel,'prepare_preview',side_effect=slow):
                panel.load(image.number);pump(started.is_set)
                article()
                until=time.monotonic()+.4
                while time.monotonic()<until:ui.root.update();time.sleep(.01)
                result['replaced_preview_cancelled']=cancelled.is_set()
                release.set()
            result['tk_errors']=errors
            result['passed']=(result['one_decode_per_import'] and result['playback_timers_after_rapid_resume']==1
                and result['concurrent_human_edit_preserved'] and result['replaced_preview_cancelled'] and not errors)
        return result
    finally:
        ui.stop_all();ui.root.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--measure-only',action='store_true')
    parser.add_argument('--report',type=Path);args=parser.parse_args()
    def no_network(*a,**kw):raise AssertionError('Native fixture must remain offline')
    with patch.object(socket,'socket',side_effect=no_network),patch.object(socket,'getaddrinfo',side_effect=no_network):
        results=run()
    if args.report:
        with args.report.open('x',encoding='utf-8') as stream:json.dump(results,stream,indent=2)
    print(json.dumps(results,indent=2))
    if not args.measure_only:assert results['passed'],results
