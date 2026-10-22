# Voice messages and reference-photo video

This update targets the Acer's 12 GB VRAM and 32 GB system RAM. Model files on
disk do not occupy RAM or VRAM until loaded. Current text-model retention,
reasoning policy and streaming behavior are unchanged.

## Talk to the AI and hear its text replies

- Press **Talk** to start one microphone recording, then press **Finish recording**
  or let its 60-second limit end it. The default input device records mono PCM
  locally. Stop discards the recording and stops owned workers.
- Whisper tiny.en transcribes on CPU. Text appears directly in the message box
  without a second popup. Review or edit it, then press Send yourself.
  Recording and transcription never send a message or execute its words.
- Enable **More > Speak replies for this chat** to hear subsequent text replies.
  A separate No-default consent covers this chat's bounded playback. Replies
  still appear as text; Piper speaks the exact displayed raw reply locally on
  CPU. Stop and New chat turn this option off. It is off at startup.
- **More > Read reply aloud** plays one reply after an exact-text approval.
  **More > Transcribe WAV into message** uses an existing recording without
  opening the microphone.

There is no background listening, wake word, voice cloning, automatic Send or
remote voice endpoint. Only person-operated UI controls can start these actions;
they are not tools offered to the model. Audio stays in RAM by default. No WAV
file is saved by the app's recording, speech or transcription path.

Speech output is limited to 2,000 characters and 120 seconds; longer replies
remain text only. Input supports English recordings up to 60 seconds. Tiny.en
can mishear speech, so review matters. This first version is turn-based: wait
for a reply/playback or press Stop before starting another voice message.
Microphone permission, a working default input/output device and compatible
drivers are required. Synthetic and fake-device checks do not prove every
physical microphone works.

## Photo to video

Use **Attach > Photo to video**. Choose a PNG/JPEG/WebP, inspect the normalized
pixels, and optionally hide or crop areas. Then enter a short motion description
and approve the exact prompt. The immutable edited photo is used for generation
only; it does not enable tools on an image-analysis turn or become a model path.

The fixed experimental LTX profile produces 65 frames at 24 fps, 384x256, using
30 steps. The reference is fitted with padding to preserve its full composition.
The 500-character prompt is tokenized with a 128-token cap; longer token
sequences are truncated. Use short descriptions. Both approval paths disclose
this bound.
Output is silent and appears in Artifacts with a unique generated-folder backup.
Text-only generate_video uses the same new backend. The old ModelScope files are
retained but are not a fallback; an unavailable or failing LTX job returns Error.
No model is downloaded during runtime inference.

New model choice is not a guarantee against every watermark, distorted object
or weak motion. Visual-quality and memory evidence belong to the specific test
profile, not to every prompt, resolution or competing application workload.

## Why the pieces can fit

The selected LTX 0.9.5 pipeline has separate components. Counts from local model
configs, constructed on the meta device without allocating their weights:

| Component | Parameters | Weight-only calculation |
| --- | ---: | ---: |
| T5 prompt encoder | 4,762,310,656 | FP32 17.74 GiB; NF4 minimum 2.22 GiB before nonquantized layers/scales/overhead |
| LTX transformer | 1,923,385,472 | BF16 approximately 3.58 GiB |
| Video VAE | 1,246,913,522 | BF16 approximately 2.32 GiB |

The encoder is quantized to NF4 in its own nested worker. It returns exactly
4 MiB of finite float32 embedding bytes plus 256 mask bytes; its process must
exit before the renderer loads with no text encoder/tokenizer. No CUDA tensors
or shared-storage handles cross that pipe. CPU offload moves components as needed.
Temporal VAE decoding uses 16-frame tiles with an 8-frame stride. The default
512-pixel spatial threshold exceeds this profile, so spatial tiling is not
activated here. Model weights, activations, allocator caches,
CUDA libraries and Windows overhead all count; parameter math alone is not a
peak-memory measurement.

The shared model-manager lease unloads this app's managed Ollama model and
prevents this manager from loading another while generation runs. It cannot
evict other applications' GPU models. Admission needs 8 GiB free system RAM and
9 GiB free VRAM. A sampled RAM guard stops our job near a 2 GiB system reserve;
the outer worker has a 16 GiB Windows commit ceiling (including descendants),
the encoder also has its own 12 GiB ceiling, and the job has a ten-minute deadline and an 82%
PyTorch allocator fraction. These checks can refuse; they are not a guarantee
against every global memory spike or driver allocation.

The Piper voice file is 63,201,294 bytes. Whisper's approximately 78 MB local
assets were already installed. Both run on CPU, using zero CUDA inference memory.
In a short synthetic round trip, sampled child working sets peaked around
156 MiB for Piper and 232 MiB for Whisper. Piper took 2.72 seconds to synthesize
3.04 seconds of audio; transcription took 5.27 seconds and recovered the test
sentence and number 42. These are single-run samples, not hard maximums.

The same speech pair also passed while gemma4:12b stayed resident with an
8,192-token context and the normal full tool menu. No tool calls were executed
in that synthetic check. It does not prove every long conversation or every
other process can fit simultaneously. Worker ceilings do not reserve that amount
of RAM: Piper synthesis uses a 1.5 GiB commit ceiling, playback 128 MiB and the
existing Whisper decoder 4 GiB, despite much smaller sampled working sets.

## Installation and model selection

The installed media-capable runtime adds pinned Piper, sounddevice,
bitsandbytes and SentencePiece packages; existing Torch/NumPy pins remain.
For another machine, install requirements-computer.txt into its chosen Python
3.12 environment. Run setup_media.py speech and setup_media.py video_ltx as
person-run setup commands. Default all setup includes audio, image, video_ltx
and speech; it skips the old video backend. Keep the upstream model licenses
and model cards with the cache. Models and runtime environments remain git-ignored.

The full LTX download is about 25.39 GB because the publisher's T5 shards are
FP32 on disk; runtime quantization does not shrink their downloaded files.
That is disk consumption, not simultaneous RAM/VRAM use. The development
download needed transport recovery; every large weight passed publisher SHA-256
verification before manifest creation. Weights load
locally from the approved manifest, with no remote code or runtime downloads.

The 2B LTX family was selected for a bounded laptop trial. Full-precision 13B
video transformers alone need roughly 26 GB of weights; the larger Wan and
Hunyuan stacks add sizable encoders/VAEs and require more aggressive offload or
quantization. They were not downloaded or benchmarked for this update. This is
a practical candidate selection, not a head-to-head claim of best visual quality.

## References and verification

- [LTX 0.9.5 publisher model card](https://huggingface.co/Lightricks/LTX-Video-0.9.5)
- [Diffusers LTX support and memory optimizations](https://huggingface.co/docs/diffusers/api/pipelines/ltx_video)
- [Supported bitsandbytes platforms](https://huggingface.co/docs/bitsandbytes/installation)
- [Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md)
- [Selected voice card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD)
- [Python 3.12 WAV-memory playback](https://docs.python.org/3.12/library/winsound.html)

The added offline suite covers consent, exact reference bytes, dictionary/format
bounds, CPU-only speech, encoder release order, low-memory refusal, RAM reserve,
Stop, opt-in playback and no auto-send. Native Tk checks exercise the new controls
using fake microphone/inference, actual media codecs and the existing approval
dialogs. All 283 offline assertions across fifteen suites and five native suites
pass. Actual speech synthesis/transcription and silent Windows playback also
passed with chat_window imported by the parent and spawned workers, matching
the app bootstrap. A personal microphone/device test remains outstanding.

Two synthetic 65-frame video trials both decoded all frames at 384x256 and
24 fps (about 2.71 seconds). Sampled figures on this laptop:

| Trial | Elapsed | Total GPU use (NVML) | Sum of worker working sets | Minimum system RAM available |
| --- | ---: | ---: | ---: | ---: |
| Text to video | 95.16 s | 4.67 GiB | 7.42 GiB | 4.22 GiB |
| Generated reference image to video | 94.30 s | 7.10 GiB | 7.51 GiB | 4.09 GiB |

These are sampled peaks under the development workload, not hard maxima.
Working-set sums can count shared pages more than once; process commit is a
different measure (approximately 15 GiB in these trials). PyTorch measurements
report the maximum of the separate encoder/renderer stages and exclude some
driver allocations; NVML samples total GPU usage including other applications.
Admission can still refuse on a busier laptop. Future resolutions need new tests.

An additional unpatched production-profile reference run imported chat_window
in the parent and each spawned worker, matching GUI startup. It passed in
97.16 seconds, decoded 65 frames, peaked at 7.10 GiB sampled total GPU usage
and 7.51 GiB summed child working sets, and retained at least 4.11 GiB available
system RAM. Its sampled private commit peaked around 15.50 GiB, close to the
16 GiB ceiling: a different driver/workload may still refuse safely. Normal
desktop launches should use the media-capable environment, not a Python lacking
the optional dependencies. The supplied local media launcher selects that runtime.

Earlier same-process loading failed under 12 and 16 GiB commit limits. Components
loaded separately; terminating the encoder process before rendering fixed that
loading path. An explicit bounded wait and exit check prevent overlap. A separate
image-to-video decode failure required a CUDA generator rather than a CPU one.
All failed trials published no completed output. The first 33-frame clips fit
memory but were nearly static; temporal decoding allowed a longer 65-frame profile
with clearer motion at a similar measured cost.

Inspected frames 0, 32 and 64 show visible motion, soft detail and object distortion;
the ball can leave the frame quickly. No obvious watermark appeared in those
inspected frames. This is a useful experimental feature, not a quality guarantee
or a broad comparison against other video models.
