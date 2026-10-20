"""Person-operated local English speech; bounded push-to-talk, no model tool or downloads."""
from io import BytesIO
import json
import wave
import time
from process_guard import Worker
from media_assets import local_asset

MAX_TEXT = 2000
MAX_WAV = 6_000_000
MAX_SECONDS = 120
VOICE = "en/en_US/lessac/medium/en_US-lessac-medium.onnx"


def text_problem(text):
    if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or
            any(not c.isprintable() and c not in "\n\t" for c in text)):
        return "speech text must be 1 to 2000 characters without control codes"
    return ""


def validate_wav(data):
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_WAV:
        raise ValueError("speech audio exceeds its byte limit")
    with wave.open(BytesIO(data), "rb") as audio:
        if (audio.getsampwidth() != 2 or audio.getnchannels() != 1 or
                not 8000 <= audio.getframerate() <= 48000 or
                not 0 < audio.getnframes() / audio.getframerate() <= MAX_SECONDS):
            raise ValueError("speech audio is outside its PCM/duration limits")
        if len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2:
            raise ValueError("speech audio is truncated")
        return audio.getnframes() / audio.getframerate()


def _synthesize(connection, initial):
    text = initial["text"]
    if text_problem(text):
        raise ValueError("invalid speech request")
    from piper import PiperVoice, PiperConfig
    import onnxruntime
    model = local_asset("speech") / VOICE
    config = json.loads(model.with_suffix(".onnx.json").read_text(encoding="utf-8"))
    if config.get("phoneme_type") != "espeak" or config.get("espeak", {}).get("voice") != "en-us":
        raise ValueError("only the fixed local English voice is allowed")
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    voice = PiperVoice(config=PiperConfig.from_dict(config), session=onnxruntime.InferenceSession(
        str(model), sess_options=options, providers=["CPUExecutionProvider"]))
    voice.use_tashkeel = False  # Never load optional Arabic diacritizer resources.
    buffer = BytesIO()
    with wave.open(buffer, "wb") as audio:
        voice.synthesize_wav(text, audio)
    data = buffer.getvalue()
    seconds = validate_wav(data)
    connection.send({"wav": data, "seconds": seconds})


def _play(connection, initial):
    data = initial["wav"]
    validate_wav(data)
    import winsound
    # Synchronous playback is the default (flag 0); Python 3.12 exposes no SND_SYNC.
    winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
    connection.send({"played": True})


def prepare_speech(text, stop_event=None):
    problem = text_problem(text)
    if problem:
        return {"error": problem}
    if stop_event is not None and stop_event.is_set():
        return {"error": "stopped by the user"}
    try:
        local_asset("speech")
        from media_resources import require_ram
        require_ram(2)
        worker = Worker(_synthesize, {"text": text}, memory_mb=1536)
        try:
            return worker.receive(45, stop_event)
        finally:
            worker.stop()
    except Exception:
        return {"error": "local speech unavailable; check the installed English voice and dependencies"}


def speak(text, stop_event=None):
    result = prepare_speech(text, stop_event)
    if "error" in result:
        return "Error: " + str(result["error"])
    if stop_event is not None and stop_event.is_set():
        return "Error: stopped by the user"
    try:
        validate_wav(result["wav"])
        worker = Worker(_play, {"wav": result["wav"]}, memory_mb=128)
        try:
            played = worker.receive(MAX_SECONDS + 5, stop_event)
        finally:
            worker.stop()
        return "Speech playback completed locally; no audio file was saved." if played.get("played") is True else "Error: speech playback stopped or unavailable."
    except Exception:
        return "Error: speech playback unavailable."


def transcribe_wav(path, stop_event=None):
    """The person chooses a WAV; return a draft for review, never execute its words."""
    from pathlib import Path
    from media_input import prepare_media
    if Path(path).suffix.lower() != ".wav":
        raise ValueError("choose a WAV recording")
    media = prepare_media(path, stop_event)
    prefix = "Untrusted local audio transcript:\n"
    if not media.observation.startswith(prefix):
        raise ValueError("invalid transcript result")
    text = media.observation[len(prefix):].strip()
    if not text or len(text) > 6000:
        raise ValueError("no bounded English transcript was returned")
    return text


def _record(connection, initial):
    """Only an explicit person-started job may open the default microphone."""
    import sounddevice
    done = initial["done"]
    info = sounddevice.query_devices(kind="input")
    rate = int(info["default_samplerate"])
    if not 8000 <= rate <= 48000 or info["max_input_channels"] < 1:
        raise ValueError("microphone format is unsupported")
    chunks, count, problems = [], 0, []
    limit = rate * 2 * 60
    def capture(data, frames, stamp, status):
        nonlocal count
        if status:
            problems.append(True); done.set(); return
        body = bytes(data)
        if count + len(body) > limit:
            done.set(); return
        count += len(body)
        chunks.append(body)
    with sounddevice.RawInputStream(samplerate=rate, channels=1, dtype="int16", blocksize=1024, callback=capture):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not done.wait(.1):
            pass
    if problems or count < rate * 2 / 5:
        raise ValueError("recording failed or was too short")
    buffer = BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(rate)
        audio.writeframes(b"".join(chunks))
    connection.send({"wav": buffer.getvalue()})


def capture_and_transcribe(done, stop_event=None, on_recorded=None):
    if stop_event is not None and stop_event.is_set():
        raise ValueError("stopped by the user")
    from media_resources import require_ram
    require_ram(2)
    worker = Worker(_record, {"done": done}, memory_mb=256)
    try:
        result = worker.receive(65, stop_event)
    finally:
        worker.stop()
    if "error" in result or (stop_event is not None and stop_event.is_set()):
        raise ValueError("recording stopped or unavailable")
    if on_recorded is not None:
        on_recorded()
    from media_input import prepare_media_bytes
    media = prepare_media_bytes(result["wav"], "wav", stop_event)
    prefix = "Untrusted local audio transcript:\n"
    if not media.observation.startswith(prefix):
        raise ValueError("invalid transcript")
    text = media.observation[len(prefix):].strip()
    if not text or len(text) > 6000:
        raise ValueError("no bounded English transcript was returned")
    return text
