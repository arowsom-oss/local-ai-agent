# Next improvements, October 21, 2026

The app routes work between separate installed local models. Their weights have
not been fused, and there is no new expert-weight streaming implementation.
Previous measured gains removed context-triggered reloads and duplicate media
decoding. The list below starts from the current supervised prototype; it does
not claim all ten improvements are implemented.

| Priority | Improvement | Concrete work and acceptance evidence | Status |
| --- | --- | --- | --- |
| 1 | Faster simple replies | Skip classifier inference for a whole bare greeting; keep real reply inference, retained reasoning, tool gates and timing. Compare repeated warm Auto/manual turns. | Implemented and measured below |
| 2 | Better context budgeting | Account for system prompt, schemas, history, current tool results and reply allowance; compare estimates with actual prompt counts. Compact eligible old turns or pause clearly before overflow. Preserve the current request and tool/result pairing. | Next implementation candidate; not started |
| 3 | More responsive Stop | Design bounded cancellation for active model/browser operations and asynchronous browser cleanup. Prove no abandoned owner worker, concurrent inference or post-Stop action. | Planned; current synchronous I/O can finish before Stop takes effect |
| 4 | Stronger source verification | Track opened/read sources separately from snippets, expose citations and coverage gaps, and evaluate claim support on synthetic research tasks. Never label model self-assessment as verification. | Planned; topic search exists but factual accuracy is not guaranteed |
| 5 | Clearer failure recovery | Improve tool-specific guidance for invalid arguments and stale targets; pause on repeated failures with a useful explanation. Do not repair arguments silently, replay approvals or invent success. | Planned; browser_read guidance already exists |
| 6 | RAM/VRAM diagnostics | Show measured available memory, owned worker usage, active model and unload status. Distinguish sampled peaks, allocator ceilings and estimates. Measure overhead before polling continuously. | Planned; existing admission checks remain |
| 7 | Fewer repeated reads | Profile repeated document/media/browser work. Add bounded reuse only where target identity, revision/hash and lifetime can be checked; invalidate on navigation/edit/New chat. | Planned; no broad cache added |
| 8 | Clearer media job status | Display queued/running/encoding/delivery stages for the existing serialized jobs. Preserve Stop, per-job approval and resource ceilings; do not invent percentages or promise an unmeasured ETA. | Planned; no new queue or parallel GPU jobs added |
| 9 | Repeatable mixed benchmarks | Exercise representative chat, research, document and media workflows with fixed synthetic inputs; record load/prompt/generation time, failures and resource samples. Keep cold and warm runs separate. | Greeting microbenchmark complete; broad workflow benchmark still planned |
| 10 | Human quality scorecard | Run the prepared unchanged main scorecard when Alexander is ready, retaining every result. Use failures to choose the next fix before merging. | Deferred by Alexander; no new score or result row |

## First completed improvement: exact greeting route

`model_router.greeting_route_hint` matches a complete ASCII greeting of at most
40 printable characters: hi, hello, hey, good morning, good afternoon or good
evening, with optional surrounding ordinary spaces and one final . ! or ?.
It is not a prefix classifier. "hi, research Mars", suffix instructions,
control characters, Unicode lookalikes, oversized input and follow-ups such as
"continue" still take the existing path. The full original request is retained.

Fixed image/document routes and an active retained reasoning session take
precedence. A greeting does not evict a retained 12b session just to load e2b.
Otherwise an exact greeting goes directly to the fast reply model, eliminating
the classifier inference. It still receives the same full system instructions
and tool schemas, uses think=True and num_ctx=8192, generates a real reply and
passes through normal code-enforced approval/dispatch. A missing installed model
is an error; there is no download or canned-answer fallback. Manual selection is
unchanged. Route logs describe the rule without copying request text.

## Before/after evidence on this laptop

The actual run_turn path used the fixed public prompt "hi", a separate warm-up,
then six Auto/manual pairs with alternating order before and after the change.
Each measured trial started a fresh message list and used the same full tool
menu and system prompt. All proposed actions were refused by a benchmark-only
argument gate; none were attempted. Only numeric metrics, reply length/validity
and route labels were retained, without answer or hidden-reasoning payloads.

| Warm measurement, six samples per mode | Before | After |
| --- | ---: | ---: |
| Median Auto full-turn wall time | 0.7873 s | 0.5053 s |
| Median manual e2b full-turn wall time | 0.5219 s | 0.5112 s |
| Auto inference calls per trial | 2 | 1 |
| Manual inference calls per trial | 1 | 1 |

The observed Auto median fell 35.8%. This is a small sequential microbenchmark,
not a 36% speed claim for research, documents, cold loading or media generation.
No output quality improvement or peak memory reduction was measured. Token
counts and machine/cache variation remain in the raw metrics. Manual control
times were similar. The more dependable structural result is removal of exactly
one classifier call in all six updated Auto trials.

A new regression reproduced the extra inference against untouched baseline
runtime at 2ec435462bb427f7e65f0ecf147ee9bd9d05f14f, then passed after the change.
Five new cases cover real inference instead of a canned reply, exact matching,
retained/image precedence, logging/permission boundaries and a missing model.
The original four-call context-reuse test now uses a general non-greeting task
so that it still exercises classification. All 330 cases in eighteen offline
suites pass in the lean Python 3.12 environment, including injection fixtures.
No UI, media worker, model weights, tool authority or scorecard criteria changed.

Raw local reports: work/greeting_route_before_2026-10-21.json,
work/greeting_route_after_2026-10-21.json,
work/greeting_route_expected_failure.log and
work/efficiency_roadmap_verified_tests_2026-10-21/summary.json.
The public numeric traces are in benchmarks/greeting-route-2026-10-21.json;
scripts/benchmark_greetings.py can repeat the synthetic protocol against a
chosen checkout using --repo PATH --output NEW_JSON_PATH. It requires the
installed app runtime and Ollama; it is deliberately separate from offline CI.
Cold loads and model switches still cost time. Broader mixed-workflow quality,
context accounting and cancellable I/O are open work. Alexander still owns his
threat-model writing and the deliberately unfixed Copy last answer task.

## Website creation and visual previews (October 22)

Static HTML/CSS previews are implemented and tested on the feature branch:
Artifacts opens supported drafts in Preview first, with explicit Preview / Code
buttons. Existing source, unsaved edits and versions remain. The model can
create a self-contained website code Artifact; one actual local-model smoke
request opened its real visual preview. 369 offline checks and the affected
native fixtures pass. WEBSITE_PREVIEW_PLAN.md records the renderer boundary,
retained initial failure and limitations. Interactive JavaScript, multi-file
websites and publishing remain future work; this is not a general code runner.

## Private school access and assistant product plan (October 22)

REMOTE_ACCESS_PLAN.md now explicitly records one-owner browser access from school,
password/passkey plus MFA, an authenticated HTTPS gateway option, owner-bound
chat/media, honest offline status and one shared GPU broker. Remote computer
control is excluded. No service is deployed and no tunnel/account is created.

PRODUCT_FEATURE_PLAN.md adds proposed saved chats/Projects, selected-document
Q&A with citations, streaming/Stop diagnostics, opt-in memory, coding workspace,
study tools and inspectable research. It lists exact small embedding, Qwen3.5
and optional OCR model candidates, with current download sizes distinguished
from unmeasured RAM/VRAM usage. No model is downloaded or integrated. Current
Gemma defaults, capability gates and the deferred scorecard stay unchanged.

## Saved chats and Projects v1 delivered (October 22)

The first product-plan stage is implemented: explicit local chat/Artifact saves,
title search, reopen with fresh permissions and IDs, transcript export, deletion
and Project notes/grouping. No autosave, secret vault, remote sync or model tool
was added. SAVED_CHATS.md has the limits and 378-offline/10-native evidence,
retained failures and one synthetic real-model recall. Selected-document Q&A,
context/cancellation work and model comparisons remain next stages. The human
main scorecard is still deferred and no proposed model has been downloaded.
