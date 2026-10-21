# Local model routing and memory policy

Python selects only gemma4:e2b or gemma4:12b at the fixed loopback Ollama endpoint.
A fixed, bounded English wording hint selects 12b when document/note/draft nouns
and create/read/edit/save/change-style verbs occur in the first 4000 characters.
Otherwise a small tool-free JSON classifier chooses general/reasoning; malformed
output falls back to the small model. Images and video contact sheets have a
fixed small vision route, no history/tools, and returned tool requests are refused.
WAV speech uses faster-whisper-tiny.en on CPU; generation uses separate local
Diffusers workers, after releasing this app's last Ollama model.

Calls are serialized. Switching unloads the previous model before loading the
next; unload failure prevents the switch. keep_alive is 60 seconds, while Free
VRAM requests immediate release. The manager cannot evict other clients' models.
After a reasoning selection, two follow-up turns retain the larger model,
avoiding repeated classifier/reasoner swapping. Manual selection remains available.
Model selection cannot change tools, permissions, approved URLs or app scope.

Classification, replies, compaction and selected-media observations share one
explicit 8192-token runner context. This avoids reloading the same fast model
between a former 2048-token classifier and an 8192-token reply. Per-response
numeric timing logs expose load, prompt processing and generation separately;
they contain no prompt/reply/reasoning text. See PERFORMANCE.md for the measured
before/after A/B and its limits. Thinking and the 60-second retention policy
are unchanged.

The document hint is a performance choice, not semantic intent detection. It may
match an explanation/negation and miss other wording or languages. Explicit model
selection still overrides Auto. A missing larger model fails without a download;
there is no automatic mutation retry with another model after refusal.

## Document routing evidence

With the bounded document_edit helper, full-menu repeated evaluation measured
e2b at 5/12 exact document tasks and 12b at 12/12. Controls were 4/4 and 2/4;
both larger-model control failures stopped before the intended preview. This is
not a general accuracy claim. One larger-model task took 65.07 seconds.

Changing classifier guidance alone met only 3/7 fixed routing expectations; all
four document requests still selected e2b. The code hint met 7/7: four document
requests chose 12b without inference, three general probes used the classifier
and chose e2b. These are seven fixed probes, not a broad router benchmark.
An actual Auto append then selected 12b for all four model requests, obtained
one exact fixture save approval and retained the earlier version in 21.14 seconds.
See RELIABILITY.md for failures, setup and scope. Test callbacks stay outside UI.

A subsequent read-format/quote fix, without a routing change, measured 12b at
11/12 document tasks and 4/4 controls. The old stale failures were now exercised
and passed; a different append proposal was denied and remains failed. The
initial 12/12 task sample above is historical, not a current perfect-score claim.

## Measurements from this laptop

Single development runs on an RTX 5070 Ti Laptop GPU (12 GB) and approximately
32 GB system RAM; timings are examples, not performance or quality guarantees.

| Check | Result | Elapsed |
| --- | --- | --- |
| Earlier synthetic vision | Read TEST SCREEN and STATUS: READY | 20.00 s |
| Earlier switch to 12b: 17 + 25 | 42 | 10.59 s |
| Actual Ollama scratch Notepad workflow | Started/read owned classic Notepad; exact approved SYNTHETIC NOTEPAD CHECK verified | 15.57 s |
| Actual Ollama practice workflow | Started/read practice app; proposed approved SYNTHETIC TEST draft; state verified | 32.73 s |
| Local image generation | Valid 512x512 PNG | 32.89 s |
| Earlier ModelScope video | Valid 256x256, 16-frame, 8-fps MP4; watermark-like output | 37.93 s |
| WAV smoke check | Transcribed synthetic English speech, including the number 42 | 4.64 s source clip |

Model check evaluated four fixed synthetic prompts on each model: three arithmetic
questions plus one strict-output classification question. The result was 7/8
exact matches. The small model failed the classifier's required one-word output;
the arithmetic answers and larger-model classifier matched. This is far too small
to establish general quality or production routing accuracy.

Small-model cold request: 25.27 s; subsequent requests approximately 0.18-0.41 s.
Large-model cold request: 13.96 s; subsequent requests approximately 0.24-0.25 s.
The report stores server-reported size_vram when available; this is not a measured
peak GPU-memory profile and should not be interpreted as one. Model check uses
only fixed synthetic text, has no tools and releases models afterward.

## Weight swapping recommendation

Keep whole-model routing and unloading for now. Arbitrarily dropping weights
from a dense model is not supported here. A trained mixture-of-experts model
and a backend with expert offload are different designs, with their own storage,
memory and latency requirements. This implementation does not stream selected
experts or claim that e2b is a removable subset of 12b. CPU offload is used only
by the fixed video pipeline; larger Ollama offload configurations are unmeasured.

The video backend was selected to fit a small experimental workload. An initial
larger download was abandoned; its partial cache remains on the development
machine after cleanup was blocked. Weights and environments are excluded from
the source package. Runtime workers use local-only loading; this is an inference
configuration rather than an OS firewall. Model accuracy, interpretation privacy
and performance under competing GPU workloads remain limitations.

## Voice and replacement video profile (October 20, 2026)

Person-operated Talk uses existing Whisper tiny.en on CPU; Piper's fixed English
voice also uses CPU. These operations do not load a second CUDA model or enter
the model's tool menu. A short real synthesis/transcription check passed while
gemma4:12b remained resident with the normal 8,192-token context and tool menu.
This single check does not establish every conversation's peak memory use.

The replacement experimental video backend is fixed LTX 0.9.5 2B, including
reference-photo input. Its NF4 T5 prompt encoder's owned process exits before loading the
BF16 renderer with CPU offload and VAE tiling. A manager lease holds the same
lock used by chat inference while releasing this app's Ollama model and running
generation. It does not unload another application's model. RAM/VRAM admission,
an owned worker commit ceiling and a sampled system-RAM reserve can refuse or
stop a job. Current retention, reasoning and streaming settings are unchanged.
See VOICE_AND_REFERENCE.md for calculations and qualification limits. The
256x256 ModelScope video measurement above remains historical; its retained
cache is not a runtime fallback.

The selected 65-frame, 384x256, 24-fps profile uses temporal VAE tiles of 16
sample frames with stride 8. Synthetic text/reference trials took 95.16/94.30
seconds, with sampled total NVML GPU usage of 4.67/7.10 GiB. Both decoded all
65 frames. They showed motion but soft details and object distortion; they are
not evidence of broad output quality. Current profile limits and later app-
bootstrap checks are recorded in VOICE_AND_REFERENCE.md.
