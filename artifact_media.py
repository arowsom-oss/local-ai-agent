"""Decode immutable local media bytes in a stoppable, bounded Windows worker."""
from io import BytesIO
from artifacts import MAX_MEDIA
from process_guard import Worker


def _decode(connection, initial):
    data, kind = initial["data"], initial["kind"]
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_MEDIA:
        raise ValueError("invalid media bytes")
    if kind == "image":
        from vision_input import prepare_image
        connection.send({"frames": [(0.0, prepare_image(data))]})
        return
    if kind != "video":
        raise ValueError("unsupported preview kind")
    import av
    from vision_input import _normalize
    frames, size = [], 0
    with av.open(BytesIO(data), format="mp4", options={"protocol_whitelist": "pipe,data"}) as container:
        streams = container.streams.video
        if len(streams) != 1 or container.duration is None or not 0 < container.duration / av.time_base <= 10:
            raise ValueError("artifact video preview supports one stream and at most 10 seconds")
        stream = streams[0]
        stream.thread_count = 2
        if not 0 < stream.width * stream.height <= 1_048_576:
            raise ValueError("artifact video resolution exceeds preview bounds")
        for index, frame in enumerate(container.decode(stream)):
            if index >= 120 or not 0 < frame.width * frame.height <= 1_048_576:
                raise ValueError("artifact video exceeds its decode bounds")
            if frame.time is None or not 0 <= frame.time <= 10 or (frames and frame.time < frames[-1][0]):
                raise ValueError("invalid frame timestamps")
            image = _normalize(frame.to_image(), "Local artifact frame")
            size += len(image.png)
            if size > 12_000_000:
                raise ValueError("decoded preview exceeds 12 MB")
            frames.append((frame.time, image))
    if not frames:
        raise ValueError("no readable video frames")
    connection.send({"frames": frames})


def prepare_preview(kind, data, stop_event=None):
    worker = Worker(_decode, {"kind": kind, "data": data}, memory_mb=512)
    try:
        result = worker.receive(15, stop_event)
        if "error" in result:
            raise ValueError("media preview stopped, invalid or unavailable")
        return result["frames"]
    finally:
        worker.stop()
