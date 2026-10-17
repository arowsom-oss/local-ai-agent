"""Metadata-only persistent audit records; no claim of detecting every secret."""


def private_arguments(args):
    if isinstance(args, dict):
        return {"redacted": True, "field_count": len(args)}
    return {"redacted": True, "argument_type": type(args).__name__}


def private_note(note):
    return f"[redacted; {len(str(note))} characters]"
