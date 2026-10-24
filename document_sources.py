"""Person-selected local document snapshots; bounded parser worker, no extraction/actions."""
from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
from pathlib import Path
import stat

from process_guard import Worker

MAX_FILE=8_000_000
MAX_PAGES=100
MAX_TEXT=200_000
MAX_PAGE=20_000


@dataclass(frozen=True)
class Source:
    number:int
    name:str
    kind:str
    digest:str
    pages:tuple

    def location(self,page):
        return f'{self.name} · '+(f'PDF page {page}' if self.kind=='pdf' else 'text notes (unpaginated)')


def clean_text(text):
    if not isinstance(text,str):raise ValueError('Invalid extracted text')
    return ''.join(c for c in text if c.isprintable() or c in '\n\r\t')


def read_selected(filename):
    """Called inside the worker only. No paths supplied by a model."""
    if not isinstance(filename,str) or filename.startswith('\\\\'):
        raise ValueError('Select a local PDF, TXT or Markdown file')
    path=Path(filename)
    if not path.is_absolute() or path.suffix.lower() not in {'.pdf','.txt','.md'} or ':' in path.name:
        raise ValueError('Select a local PDF, TXT or Markdown file')
    if os.name=='nt':
        import ctypes
        get_drive=ctypes.WinDLL('kernel32',use_last_error=True).GetDriveTypeW
        get_drive.argtypes=[ctypes.c_wchar_p];get_drive.restype=ctypes.c_uint
        if get_drive(path.anchor) not in (2,3,5,6):raise ValueError('Use a local drive, not a network location')
    for part in (path,*path.parents):
        info=part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024:
            raise ValueError('Linked, cloud-placeholder or junction source paths are refused')
    before=path.stat()
    if not stat.S_ISREG(before.st_mode) or not 1<=before.st_size<=MAX_FILE:
        raise ValueError('Select a regular file of at most 8 MB')
    with path.open('rb') as file:
        opened=os.fstat(file.fileno());data=file.read(MAX_FILE+1);after=os.fstat(file.fileno())
    signature=lambda info:(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
    if len(data)>MAX_FILE or signature(before)!=signature(opened) or signature(opened)!=signature(after) or signature(after)!=signature(path.stat()):
        raise ValueError('Source changed while reading; select it again')
    return data,path.name,path.suffix.lower()


def parse_pdf(data,reader_factory=None):
    if not data.startswith(b'%PDF-'):raise ValueError('File is not a PDF')
    if reader_factory is None:
        from pypdf import PdfReader
        reader_factory=PdfReader
    reader=reader_factory(BytesIO(data),strict=True)
    if reader.is_encrypted:raise ValueError('Encrypted PDFs are unsupported; choose a readable copy')
    if not 1<=len(reader.pages)<=MAX_PAGES:raise ValueError('PDF must have 1–100 pages')
    pages=[];total=0
    for page in reader.pages:
        text=clean_text(page.extract_text() or '')
        total+=len(text)
        if len(text)>MAX_PAGE or total>MAX_TEXT:raise ValueError('PDF exceeds extracted-text limits; select a smaller document')
        pages.append(text)
    if not any(text.strip() for text in pages):
        raise ValueError('No readable text found. Scanned PDFs need OCR; this version has no OCR')
    return tuple(pages)


def _parse(connection,initial):
    try:
        data,name,suffix=read_selected(initial)
        if suffix=='.pdf':pages=parse_pdf(data);kind='pdf'
        else:
            text=clean_text(data.decode('utf-8-sig',errors='strict'))
            if not text.strip() or len(text)>MAX_TEXT:raise ValueError('Notes must contain 1–200000 characters of UTF-8 text')
            pages=(text,);kind='text'
        connection.send(dict(name=clean_text(name)[:120],kind=kind,digest=hashlib.sha256(data).hexdigest(),pages=pages))
    except ValueError as exc:connection.send({'error':str(exc)[:250]})
    except Exception:connection.send({'error':'Document is unreadable, malformed or the PDF parser is unavailable'})


def import_source(filename,number,stop_event):
    if type(number) is not int or number<1:raise ValueError('Invalid source number')
    if stop_event.is_set():raise ValueError('Import cancelled')
    worker=None
    try:
        worker=Worker(_parse,filename,memory_mb=768)
        result=worker.receive(20,stop_event)
        if stop_event.is_set():raise ValueError('Import cancelled')
        if not isinstance(result,dict):raise ValueError('Invalid parser result')
        if 'error' in result:raise ValueError(str(result['error'])[:250])
        if set(result)!={'name','kind','digest','pages'}:raise ValueError('Invalid parser result')
        name,kind,digest,pages=(result[key] for key in ('name','kind','digest','pages'))
        if (not isinstance(name,str) or not 1<=len(name)<=120 or not name.isprintable()
                or kind not in ('pdf','text') or not isinstance(digest,str) or len(digest)!=64
                or any(c not in '0123456789abcdef' for c in digest)
                or not isinstance(pages,tuple) or not 1<=len(pages)<=MAX_PAGES
                or (kind=='text' and len(pages)!=1)
                or any(not isinstance(p,str) or clean_text(p)!=p or len(p)>(MAX_PAGE if kind=='pdf' else MAX_TEXT) for p in pages)
                or sum(map(len,pages))>MAX_TEXT or not any(p.strip() for p in pages)):
            raise ValueError('Invalid or oversized parser result')
        return Source(number,name,kind,digest,pages)
    finally:
        if worker is not None:worker.stop()
