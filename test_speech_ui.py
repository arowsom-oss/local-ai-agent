"""Native Tk voice/reference controls with fake microphone/inference; no personal audio captured."""
from io import BytesIO
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from PIL import Image
import av
import chat_window as ui
import generation_tools
import speech_tools
from vision_input import prepare_image


def pump(test, timeout=15):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        ui.root.update()
        if test():return
        time.sleep(.02)
    raise AssertionError('Speech UI fixture timed out')


if __name__=='__main__':
    with patch('emergency_hotkey.start_hotkey'):
        ui.build_window()
    ui.root.geometry('1280x800');errors=[]
    ui.poll()
    ui.root.report_callback_exception=lambda kind,value,trace:errors.append(value)
    try:
        ui.root.update()
        assert ui.mic_button.winfo_ismapped() and not ui.voice_auto.get() and not ui.speak_replies
        # Talk and transcript staging need no popup. Send remains a separate gesture.
        with patch.object(ui,'high_risk_confirm',side_effect=AssertionError('No dictation popups')), \
                patch.object(speech_tools,'capture_and_transcribe',return_value='Synthetic voice message.'), \
                patch.object(ui,'run_turn',side_effect=AssertionError('Transcript must not send itself')):
            ui.voice_message()
            pump(lambda:not ui.busy and ui.entry.get()=='Synthetic voice message.')
        assert ui.mic_button.cget('text')=='Talk'
        ui.stage_dictation('Do not replace this draft.')
        assert ui.entry.get()=='Synthetic voice message.'
        ui.entry.delete(0,'end')
        ui.stop_event.set();ui.stage_dictation('Discard cancelled recording.')
        assert not ui.entry.get()
        ui.stop_event.clear()
        # Choose a different model during a running job; the current turn's
        # captured model stays unchanged and the next turn uses the new choice.
        captured=[];release=__import__('threading').Event()
        def fake_turn(*args):
            captured.append(args[1]);release.wait(3)
            ui.events.put(('answer','Synthetic selection reply.',.01))
        with patch.object(ui,'worker',side_effect=fake_turn):
            ui.model_var.set('gemma4:e2b');ui.entry.insert(0,'Synthetic model selection test')
            ui.send();pump(lambda:bool(captured))
            assert str(ui.model_box.cget('state'))=='readonly'
            ui.model_box.event_generate('<Button-1>',x=ui.model_box.winfo_width()-8,y=10)
            ui.root.update()
            pop=ui.root.tk.call('ttk::combobox::PopdownWindow',str(ui.model_box))
            assert ui.root.tk.call('winfo','ismapped',pop)
            listing=pop+'.f.l'
            ui.root.tk.call(listing,'selection','clear',0,'end')
            ui.root.tk.call(listing,'selection','set',2)
            ui.root.tk.call('ttk::combobox::LBSelected',listing)
            assert ui.model_var.get()=='gemma4:12b'
            release.set();pump(lambda:not ui.busy)
            assert captured==['gemma4:e2b']
            ui.entry.insert(0,'Synthetic next model selection test');ui.send()
            pump(lambda:len(captured)==2 and not ui.busy)
            assert captured==['gemma4:e2b','gemma4:12b']
        # Opt-in auto speech reads exactly the visible model reply using the CPU path.
        spoken=[]
        ui.voice_auto.set(True)
        with patch.object(ui,'high_risk_confirm',return_value=True):ui.toggle_spoken_replies()
        assert ui.speak_replies
        with patch.object(speech_tools,'speak',side_effect=lambda text,stop:spoken.append(text) or 'Speech completed.'):
            ui.events.put(('answer','Synthetic reply for speech.',.1))
            pump(lambda:spoken==['Synthetic reply for speech.'] and not ui.busy)
        ui.stop_agent()
        assert not ui.speak_replies and not ui.voice_auto.get()
        ui.stop_event.clear()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);reference=root/'reference.png'
            Image.new('RGB',(256,256),'teal').save(reference)
            clip=root/('c'*32+'.mp4')
            with av.open(str(clip),'w') as container:
                stream=container.add_stream('libx264',rate=8);stream.width=stream.height=256;stream.pix_fmt='yuv420p'
                for index in range(16):
                    for packet in stream.encode(av.VideoFrame.from_image(Image.new('RGB',(256,256),(0,index*12,100)))):
                        container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            pixels=prepare_image(reference.read_bytes())
            from tkinter import simpledialog
            def preview(image,on_approve,purpose):
                assert purpose=='video';on_approve(pixels);return True
            def generate(kind,prompt,stop,reference):
                assert kind=='video' and prompt=='Gentle movement.' and reference is pixels
                return {'path':str(clip)}
            with patch.object(ui.filedialog,'askopenfilename',return_value=str(reference)), \
                    patch.object(ui,'preview_image',side_effect=preview), \
                    patch.object(simpledialog,'askstring',return_value='Gentle movement.'), \
                    patch.object(ui,'confirm',return_value=True), \
                    patch.object(generation_tools,'OUTPUT_DIR',root), \
                    patch.object(generation_tools,'run_generation',side_effect=generate):
                ui.animate_photo()
                pump(lambda:not ui.busy and ui.artifact_panel.selected is not None and len(ui.artifact_panel.frames)==16)
            assert ui.artifacts_visible() and ui.artifact_panel.selected.kind=='video'
        with patch.object(ui.messagebox,'askyesno',return_value=True),patch.object(ui,'free_vram'):
            ui.new_chat()
        assert not ui.speak_replies and not ui.voice_auto.get()
        assert not errors,errors
        print('PASS native voice/reference UI: no dictation popups, editable unsent transcript, draft/Stop protection, native model dropdown/current-next turn, spoken reply opt-in and reference Artifacts.')
    finally:
        ui.stop_all();ui.root.destroy()
