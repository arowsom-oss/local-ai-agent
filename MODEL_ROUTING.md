# Local model routing and memory policy

Python selects only gemma4:e2b or gemma4:12b at the fixed loopback Ollama endpoint.
A small tool-free JSON classifier chooses general/reasoning for text; malformed
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
| Local video generation | Valid 256x256, 16-frame, 8-fps MP4 | 37.93 s |
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
