"""Local Studio window branding. Never change system-wide Python file associations."""
import ctypes
import os
from pathlib import Path
import tkinter as tk

APP_ID='LocalStudio.PrivateAgent.Desktop'
ICON=Path(__file__).resolve().parent/'assets/local-studio.ico'


def set_app_identity():
    if os.name=='nt':
        try:
            shell=ctypes.WinDLL('shell32')
            shell.SetCurrentProcessExplicitAppUserModelID.argtypes=[ctypes.c_wchar_p]
            return shell.SetCurrentProcessExplicitAppUserModelID(APP_ID)==0
        except (OSError,AttributeError):return False
    return False


def set_window_icon(root):
    try:
        if os.name=='nt':
            root.iconbitmap(default=str(ICON));root.iconbitmap(str(ICON))
        else:
            image=tk.PhotoImage(file=str(ICON.with_suffix('.png')))
            root.iconphoto(True,image);root._brand_image=image
        return True
    except (OSError,tk.TclError):return False
