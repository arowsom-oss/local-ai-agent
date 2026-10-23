"""Bounded single-member ZIP payloads. Never extract names or accept model paths."""
from io import BytesIO
import time
import zipfile
import zlib

MAX_BYTES=96_000_000
MEMBER='chat.json'


def unpack(payload):
    if isinstance(payload,str):
        if len(payload.encode('utf-8'))>MAX_BYTES:raise ValueError('Oversized saved chat')
        return payload
    if not isinstance(payload,bytes) or not 1<=len(payload)<=MAX_BYTES:
        raise ValueError('Invalid ZIP chat payload')
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            members=archive.infolist()
            if len(members)!=1:raise ValueError('ZIP chat must have one member')
            info=members[0]
            if (info.filename!=MEMBER or info.is_dir() or info.flag_bits&1
                    or info.compress_type!=zipfile.ZIP_DEFLATED or not 1<=info.file_size<=MAX_BYTES):
                raise ValueError('Invalid ZIP chat member')
            with archive.open(info) as file:
                data=file.read(MAX_BYTES+1)
            if len(data)!=info.file_size or len(data)>MAX_BYTES:
                raise ValueError('ZIP chat exceeds bounds')
            return data.decode('utf-8')
    except (OSError,RuntimeError,zipfile.BadZipFile,UnicodeError,zlib.error) as exc:
        raise ValueError('ZIP chat is corrupt or unavailable') from exc


def pack(text,cancelled=lambda:False):
    """Compress chunks, verify CRC/bytes, and refuse cancellation before replacement."""
    raw=unpack(text).encode('utf-8')
    deadline=time.monotonic()+20
    output=BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        with archive.open(MEMBER,'w') as target:
            for offset in range(0,len(raw),262144):
                if cancelled() or time.monotonic()>deadline:raise ValueError('ZIP cancelled or timed out')
                target.write(raw[offset:offset+262144])
    if cancelled():raise ValueError('ZIP cancelled')
    result=output.getvalue()
    if unpack(result).encode('utf-8')!=raw:raise ValueError('ZIP verification failed')
    return result
