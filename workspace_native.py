"""Windows handle-based, append-only text workspace. No model path arguments."""
from contextlib import contextmanager, ExitStack
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import re
import uuid

MAX_BYTES=128000
FILE=re.compile(r'doc-([0-9a-f]{32})-v([0-9]{3})\.txt\Z')


class NativeFiles:
    def __init__(self,root):
        if os.name!='nt':raise ValueError('document workspace requires Windows')
        self.root=Path(root).absolute()
        self.k=C.WinDLL('kernel32',use_last_error=True)
        k=self.k
        k.GetDriveTypeW.argtypes=[W.LPCWSTR];k.GetDriveTypeW.restype=W.UINT
        if k.GetDriveTypeW(self.root.anchor)!=3:raise ValueError('workspace must be on a fixed local drive')
        k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
        k.CloseHandle.argtypes=[W.HANDLE]
        k.GetFileInformationByHandle.argtypes=[W.HANDLE,C.c_void_p]
        k.ReadFile.argtypes=[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p]
        k.WriteFile.argtypes=k.ReadFile.argtypes
        k.FlushFileBuffers.argtypes=[W.HANDLE]
        k.SetFileInformationByHandle.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
        k.SetFilePointerEx.argtypes=[W.HANDLE,C.c_int64,C.c_void_p,W.DWORD]

    @contextmanager
    def handle(self,path,access,share,creation=3,directory=False):
        flags=0x00200000 | (0x02000000 if directory else 0) # OPEN_REPARSE_POINT, BACKUP_SEMANTICS
        h=self.k.CreateFileW(str(path),access,share,None,creation,flags,None)
        if h==C.c_void_p(-1).value:raise OSError('workspace file is unavailable or locked')
        try:
            self.info(h,directory)
            yield h
        finally:self.k.CloseHandle(h)

    def info(self,h,directory=False):
        class Info(C.Structure):
            _fields_=[('attrs',W.DWORD),('created',W.FILETIME),('accessed',W.FILETIME),('written',W.FILETIME),
                ('volume',W.DWORD),('high',W.DWORD),('low',W.DWORD),('links',W.DWORD),('index_high',W.DWORD),('index_low',W.DWORD)]
        info=Info()
        if not self.k.GetFileInformationByHandle(h,C.byref(info)):raise OSError('workspace identity check failed')
        if info.attrs & 0x400 or bool(info.attrs & 0x10)!=directory:raise ValueError('links, reparse points and unexpected file types are refused')
        if not directory and (info.links!=1 or info.high or info.low>MAX_BYTES):raise ValueError('linked or oversized workspace file refused')
        return info.low

    @contextmanager
    def locked(self):
        # Pin every existing ancestor against rename/removal; reject junctions as well as symlinks.
        with ExitStack() as stack:
            parts=list(reversed(self.root.parents))+[self.root]
            for path in parts:
                if path==self.root:
                    path.mkdir(exist_ok=True)
                stack.enter_context(self.handle(path,0x80,3,directory=True))
            yield

    def inventory(self):
        groups={}
        with os.scandir(self.root) as entries:
            for index,entry in enumerate(entries):
                if index>=300:raise ValueError('workspace directory entry limit reached')
                match=FILE.fullmatch(entry.name)
                if match:
                    key,version=match.group(1),int(match.group(2))
                    if not 1<=version<=12:raise ValueError('workspace version is out of bounds')
                    # Opening checks identity/type/size without following reparse points.
                    with self.handle(self.root/entry.name,0x80000000,1):pass
                    groups.setdefault(key,[]).append(version)
        if len(groups)>20:raise ValueError('20 document limit reached')
        for versions in groups.values():
            if sorted(versions)!=list(range(1,max(versions)+1)):raise ValueError('workspace history has a missing version; recover it manually')
        return {key:max(versions) for key,versions in groups.items()}

    def filename(self,key,version):
        name=f'doc-{key}-v{version:03}.txt'
        if not FILE.fullmatch(name) or not 1<=version<=12:raise ValueError('invalid internal document identity')
        return name

    @contextmanager
    def reader(self,key,version):
        with self.handle(self.root/self.filename(key,version),0x80000000,1) as h:
            yield self.read_handle(h)

    def read_handle(self,h):
        length=self.info(h);buf=C.create_string_buffer(length+1);count=W.DWORD()
        if not self.k.SetFilePointerEx(h,0,None,0) or not self.k.ReadFile(h,buf,length+1,C.byref(count),None):raise OSError('workspace read failed')
        if count.value!=length:raise ValueError('workspace file changed while reading')
        return buf.raw[:count.value]

    def publish(self,key,version,data,stop):
        name=self.filename(key,version)
        if not isinstance(data,bytes) or len(data)>MAX_BYTES:raise ValueError('workspace text exceeds byte limit')
        # Pending files are not documents. Publish by renaming this exact open handle,
        # with replacement disabled, only after flush and full read-back.
        pending=self.root/('.pending-'+uuid.uuid4().hex)
        with self.handle(pending,0xC0010000,0,creation=1) as h:
            published=False
            try:
                count=W.DWORD();buf=C.create_string_buffer(data)
                if not self.k.WriteFile(h,buf,len(data),C.byref(count),None) or count.value!=len(data):raise OSError('workspace write failed')
                if not self.k.FlushFileBuffers(h) or self.read_handle(h)!=data:raise OSError('workspace verification failed')
                if stop is not None and stop.is_set():raise ValueError('stopped before document publication')
                target=str(self.root/name)
                encoded=target.encode('utf-16-le')
                class Rename(C.Structure):
                    _fields_=[('replace',W.BOOL),('root',W.HANDLE),('length',W.DWORD),('name',W.WCHAR*(len(encoded)//2+1))]
                rename=Rename();rename.replace=False;rename.root=None;rename.length=len(encoded)
                C.memmove(C.addressof(rename)+Rename.name.offset,encoded,len(encoded))
                if not self.k.SetFileInformationByHandle(h,3,C.byref(rename),C.sizeof(rename)):raise OSError('new version publication refused; existing files are never overwritten')
                published=True
                if self.read_handle(h)!=data:raise OSError('published document read-back failed')
            finally:
                if not published:
                    delete=W.BOOL(True)
                    self.k.SetFileInformationByHandle(h,4,C.byref(delete),C.sizeof(delete))
        return str(self.root/name)
