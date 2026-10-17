# Local vision and model routing: first working stage

We can use the installed models as specialists without granting them different
permissions. The small model classifies the person's latest text request into
one of two roles; Python validates the JSON and maps the role to a fixed local
model. A request with a person-approved image follows a fixed vision route.
Routing does not grant consent, execute tools, choose a URL or create another
agent. All text specialists use the existing code-enforced tool boundary.

## What is implemented

| Job | Model | Boundary |
| --- | --- | --- |
| Routing and general text | gemma4:e2b | Classifier has no tools; strict role validation |
| Harder reasoning/coding | gemma4:12b | Existing tool approval rules still apply |
| Still images/screenshots | gemma4:e2b | No tools or action dispatch at all |

The window and terminal default to auto routing. The window retains manual model
selection. We show routing decisions in the chat's tool log. The classifier sees
only the newest user text, capped at 4,000 characters, not images or page history.
Its choice can be wrong, especially for follow-up questions. Invalid responses
fall back to the small model; missing models are reported, never downloaded.

All calls use the fixed loopback endpoint, ignore proxy and host environment
overrides, and refuse redirects. Only the two installed local model names are
allowed. The manager serializes its calls, requests `keep_alive="60s"`, and sends
`keep_alive=0` before switching its active model. An unload error prevents loading
another model. Free VRAM and New chat request unloading without deleting files.
Other clients using the same Ollama server can still affect memory and timing.

## Screenshot consent and limits

Screenshot asks permission to capture the primary display once, hides this chat
window briefly, and previews the prepared pixels. Attach image uses a person-run
file picker. Neither operation is available to the model. Preview defaults to No;
Enter, Escape and closing deny. Use this image stages one immutable payload for
the next Send. The person can clear it before sending. Existing pending images
remain if a replacement is cancelled; Clear image explicitly removes them.

Files are bounded to 10 MB and 20 megapixels, PNG/JPEG/WebP only, single frame.
Images are normalized to RGB PNG, metadata removed, longest side at most 1536,
and encoded payload at most 8 MB. Resizing can lose tiny UI text. The preview
shows those prepared pixels and dimensions, not the larger original. Capture
includes whatever is visible on the primary display, so close sensitive material
first. No real desktop screenshot was captured during development validation.

Image analysis receives no conversation history or tools. A returned tool call
is an error, never an action. Only the question and interpretation text are kept
in chat; image bytes and source paths are not written to history/audit/disk by
the app. The audit records dimensions and selected model only. Interpretation
can still quote sensitive text and must be treated as untrusted data on later
turns. This is not a claim of forensic erasure from Ollama caches or OS memory.

## Measurements on this laptop

These are individual smoke checks, not averages or performance guarantees. The
machine reported an RTX 5070 Ti Laptop GPU with about 12 GB VRAM and about 32 GB
system RAM. Both installed tags advertise vision and tool support.

| Check | Observed result | Elapsed |
| --- | --- | --- |
| Cold small-model classifier: greeting | general / e2b | 12.72 s |
| Warm classifier: debug thread-pool deadlock | reasoning / 12b selection | 0.28 s |
| Synthetic vision through manager | Red shape and both labels identified | 20.00 s |
| Switch to 12b and ask 17 + 25 | 42 | 10.59 s |
| Full core auto-image path after unload | Read TEST SCREEN and STATUS: READY | 14.46 s |
| Explicit release after each live sequence | Ollama ps showed no loaded models | Not benchmarked |

The 12b selection row only measures classification, not the larger model loading.
Actual output depends on resolution, prompt, context, temperature, GPU residency
and background work. These results do not establish real-time screen control,
model-routing accuracy or reliable UI coordinates. Stop cannot interrupt an
in-flight blocking call; the local client has an operation timeout, not a hard
cancel deadline.

## My recommendation on weight swapping

I recommend this whole-model routing/unloading approach first. We already have
the models and can test exactly when each is used. It is reversible and leaves
the permission boundary independent of the model. We should not promise that a
larger specialist always answers better: the routing classifier needs a broader
task evaluation set before making quality claims.

The idea of using only selected weights has two different meanings. In a dense
model we generally cannot remove arbitrary weights for a task and expect the
same model to work. Mixture-of-experts models are trained to activate selected
experts, but inactive weights still consume storage/memory unless an execution
backend explicitly offloads them. Google's Gemma guidance states that the 26B
MoE activates roughly 4B parameters per token while loading the full model for
fast inference. Its E2B model's effective parameter count uses a different
embedding design; E2B is not simply a task-selected slice of 12B.

CPU/GPU offload is another option when weights do not all fit in VRAM. Ollama
supports partial CPU/GPU placement, but moving or computing more on the CPU can
cost latency. We have not benchmarked larger offloaded models on this laptop.
We should measure a concrete need before adding custom layer/expert streaming.
Auto routing itself adds overhead: a reasoning-heavy session can repeatedly
unload 12B, load the classifier, then reload 12B. Manual 12B selection avoids that
classification churn. A future policy can add explicit user-controlled modes or
routing hysteresis after measuring real workloads.

Sources: [Ollama memory lifecycle and CPU/GPU placement](https://docs.ollama.com/faq),
[Gemma architecture and memory explanation](https://ai.google.dev/gemma/docs/core),
[Ollama image inputs](https://docs.ollama.com/capabilities/vision).

## What this stage does not add

There are no desktop clicks, typing, unattended monitoring, video input, image
generation or video generation. The next computer-use layer needs its own narrow
action API, exact target validation and user consent; reading a screenshot must
not silently grant that authority. This update is proposed on the existing draft
PR and packaged separately; the installed agent and Downloads originals remain
unchanged until the person integrates it.
