"""Known failing student-owned regression. No xfail, no application patch, no Tk/network."""
import queue
import re
import threading
from types import SimpleNamespace as NS

from adversarial_test_support import ui_functions,copy_button_command


def test_copy_last_answer_preserves_fenced_python_and_backticks_byte_for_byte():
    reply=('Keep `inline_code` and **bold markers** exactly. Café.\n\n'
           '```python\nfrom pathlib import Path\n'
           'print("literal `backticks`")\nprint("Café")\n```\n')
    clipboard=[];shown=[];entries=[]
    root=NS(clipboard_clear=lambda:clipboard.clear(),clipboard_append=clipboard.append,
            after=lambda *args:None)
    namespace=dict(queue=queue,re=re,events=queue.Queue(),root=root,last_answer='',last_raw_answer='',
        conversation_entries=entries,remove_pending=lambda:None,finish_turn=lambda:None,
        show=lambda *args:shown.append(args),speak_replies=False,stop_event=threading.Event(),
        sync_attachment_chip=lambda:None,flash_copied=lambda:None)
    ui_functions({'clean','poll','copy_text'},namespace)
    namespace['events'].put(('answer',reply,.125))
    namespace['poll']()
    assert namespace['last_raw_answer']==reply and entries==[{'role':'assistant','content':reply}]
    copy_button_command(namespace)()
    assert len(clipboard)==1,'Copy callback did not put one reply on the clipboard'
    actual=clipboard[0].encode('utf-8');expected=reply.encode('utf-8')
    assert actual==expected,('Copy last answer changed the reply bytes. '
        f'Expected {expected!r}; clipboard received {actual!r}')


if __name__=='__main__':
    assert __debug__,'Run without -O; the regression must remain a real failing assert'
    test_copy_last_answer_preserves_fenced_python_and_backticks_byte_for_byte()
    print('PASS test_copy_last_answer_preserves_fenced_python_and_backticks_byte_for_byte')
