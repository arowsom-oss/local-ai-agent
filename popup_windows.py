"""Shared close controls, bounded placement and modal-grab cleanup for Tk popups."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace


def work_area(win):
    """Use the parent's monitor work area on Windows, with a Tk fallback."""
    try:
        import ctypes as C
        from ctypes import wintypes as W
        class MonitorInfo(C.Structure):
            _fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
        user=C.WinDLL('user32',use_last_error=True)
        user.MonitorFromWindow.argtypes=[W.HWND,W.DWORD];user.MonitorFromWindow.restype=W.HANDLE
        user.GetMonitorInfoW.argtypes=[W.HANDLE,C.POINTER(MonitorInfo)]
        parent=win.master.winfo_toplevel()
        monitor=user.MonitorFromWindow(parent.winfo_id(),2)
        info=MonitorInfo();info.size=C.sizeof(info)
        if not user.GetMonitorInfoW(monitor,C.byref(info)):raise OSError('monitor unavailable')
        r=info.work
        return r.left,r.top,r.right,r.bottom
    except (AttributeError,OSError,tk.TclError):
        return 0,0,win.winfo_screenwidth(),win.winfo_screenheight()


def place_popup(win,width,height):
    left,top,right,bottom=work_area(win)
    width=max(1,min(width,right-left-40));height=max(1,min(height,bottom-top-80))
    x=left+(right-left-width)//2;y=top+(bottom-top-height)//2
    # A literal negative coordinate needs "+-N"; "-N" means a right/bottom offset.
    win.geometry(f'{width}x{height}+{x}+{y}')
    win.minsize(min(420,width),min(240,height))
    return width,height


def dismissible(win,close=None,*,button=True,label='Close',size=None):
    """Reserve a visible footer first; Escape and the title-bar X use the same close."""
    def dismiss(event=None):
        if win.winfo_exists():
            try:
                if close is not None:close()
            finally:
                if win.winfo_exists():win.destroy()
        return 'break'
    win.protocol('WM_DELETE_WINDOW',dismiss)
    win.bind('<Escape>',dismiss)
    win._dismiss_popup=dismiss
    if button:
        owner=win.master.winfo_toplevel()
        previous=getattr(owner,'_utility_popup',None)
        if previous is not None and previous is not win and previous.winfo_exists():previous._dismiss_popup()
        owner._utility_popup=win
        win.configure(bg=ttk.Style(win).lookup('TFrame','background'))
        footer=ttk.Frame(win,padding=(18,12));footer.pack(side='bottom',fill='x')
        ttk.Label(footer,text='Esc to close',style='Muted.TLabel').pack(side='left')
        ttk.Button(footer,text=label,command=dismiss).pack(side='right')
        ttk.Separator(win).pack(side='bottom',fill='x')
    if size:place_popup(win,*size)
    return dismiss


def wait_modal(root,win,focus):
    """Always release a modal grab; restore an enclosing modal if still alive."""
    previous=root.grab_current()
    try:
        win.wait_visibility();win.grab_set();focus.focus_set();root.wait_window(win)
    finally:
        try:
            if win.winfo_exists():
                if root.grab_current()==win:win.grab_release()
                win.destroy()
            if previous is not None and previous.winfo_exists() and root.grab_current() is None:
                previous.grab_set()
        except tk.TclError:pass  # The whole app may have been closed during the wait.


def scrolling_frame(parent):
    """Scrollable variable-length controls; reserve any footer before calling."""
    outer=ttk.Frame(parent);outer.pack(fill='both',expand=True)
    canvas=tk.Canvas(outer,highlightthickness=0,background=ttk.Style(parent).lookup('TFrame','background'))
    bar=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
    bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    canvas.configure(yscrollcommand=bar.set)
    body=ttk.Frame(canvas);item=canvas.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(item,width=event.width))
    def wheel(event):
        if event.delta:canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        return 'break'
    # Bind only to this popup, never globally across the app.
    parent.bind('<MouseWheel>',wheel)
    return body


def askyesno(title,message,*,parent,default='no',**options):
    """A cancellable Yes/No prompt. Windows' native Yes/No X may be disabled."""
    root=parent.winfo_toplevel();win=tk.Toplevel(root)
    win._approval_dialog=True;win.title(title);win.transient(root)
    style=ttk.Style(root);background=style.lookup('TFrame','background');foreground=style.lookup('TLabel','foreground')
    win.configure(bg=background)
    place_popup(win,680,420)
    answer=False
    def finish(allow=False):
        nonlocal answer
        answer=allow is True
        win.destroy()
    dismissible(win,finish,button=False)
    row=ttk.Frame(win,padding=12);row.pack(side='bottom',fill='x')
    ttk.Button(row,text='Yes',command=lambda:finish(True)).pack(side='left')
    no=tk.Button(row,text='No',command=finish,default='active',padx=24,pady=8,relief='flat',
                 bg=style.lookup('TButton','background'),fg=foreground)
    no.pack(side='right')
    holder=ttk.Frame(win,padding=12);holder.pack(fill='both',expand=True)
    box=tk.Text(holder,wrap='word',font=('Segoe UI',11),relief='flat',padx=12,pady=12,bg=background,fg=foreground)
    bar=ttk.Scrollbar(holder,command=box.yview);bar.pack(side='right',fill='y')
    box.configure(yscrollcommand=bar.set);box.pack(fill='both',expand=True)
    box.insert('end',str(message));box.configure(state='disabled')
    win.bind('<Return>',lambda event:finish())
    wait_modal(root,win,no)
    return answer


# Keep a small mockable interface shared by the chat and Artifact panels.
decisions=SimpleNamespace(askyesno=askyesno)
