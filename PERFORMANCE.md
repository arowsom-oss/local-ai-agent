# Auto routing: context reuse and measured latency

## Fix and measurement protocol (October 20, 2026)

The classifier previously requested num_ctx=2048, followed by a reply at 8192.
On the installed Ollama 0.40.3, this changed the runner and reloaded the same
fast model. A 100% GPU entry in ollama ps did not rule out that load cost.
The classifier, replies, media observations and compaction now use the shared
model_router.TEXT_CONTEXT value of 8192. Changing model still unloads the old
managed model first. Keep-alive, tool menu, classifier output bound, reasoning
setting and approval rules stay unchanged.

Before editing runtime code, a local harness ran the actual run_turn path:
two "hi" turns in one Auto chat, two in a separate manual gemma4:e2b chat, and
one read-only document explanation on Auto. Each mode block started without
a resident model; the second turn reused that block's history. All returned
tool calls were refused before dispatch; none were returned. No sites,
documents, desktop actions, or scorecard steps were exercised.

The same protocol ran after the fix. It collected API load/prompt/generation
durations, numeric token/thinking counts, context transitions, runner PIDs and
literal ollama ps output. Data contains no prompt, answer or reasoning payloads
from personal conversations. Fixed synthetic prompts are described above.

| Request | Before wall time | After wall time | Before summed load time | After summed load time |
| --- | ---: | ---: | ---: | ---: |
| Auto hi, second/warm turn | 19.0002 s | 0.7877 s | 17.6694 s | 0.0620 s |
| Manual hi, second/warm turn | 3.0719 s | 0.3285 s | 0.0217 s | 0.0175 s |
| Auto hi, first/cold turn | 106.1778 s | 12.8869 s | 69.2406 s | 11.3585 s |
| Manual hi, first/cold turn | 6.9606 s | 8.1006 s | 5.8881 s | 6.9609 s |
| Auto document explanation, cold 12b | 25.8542 s | 18.5454 s | 12.7807 s | 9.4563 s |

These are one short before/after A/B, not a general speed guarantee. The first
baseline request had unusually expensive loading/prompt processing. Disk/OS
caches, scheduling and generated token counts varied, including manual replies.
Do not attribute every timing difference to the fix. The strongest evidence is
the repeated Auto load component and runner identity: before, the second Auto
turn loaded at 2048 then 8192 with different active runner PIDs; afterward it
retained one runner at 8192 across classification and both replies.

The second Auto turn dropped about 96% in this sample. It still pays for the
classifier request and may re-evaluate prompts; this change removes the avoidable
context-driven model reload, not every source of latency. Cold loads still cost
seconds. Both document checks used 12b at 8192 and ollama ps showed 100% GPU;
they do not establish peak VRAM or all-document performance.

## Timing diagnostics

Each app response now emits a [timing] JSON line through the existing log
callback: classifier, normal reply/tool loop, compaction and media observation.
load_duration_s, prompt_eval_duration_s, eval_duration_s and total_duration_s
are the corresponding Ollama nanosecond values converted to seconds. Token
counts, model, requested context, reasoning setting and thinking-character
count help interpret the figures. A thinking-character count is not a separate
measurement of reasoning time. Prompt, reply and reasoning text are excluded.
Unavailable/invalid optional fields are omitted. A logging failure cannot
change or retry a completed model request. The callback is not sent to Ollama.

Normal replies retain think=True. In the baseline second Auto hi, generation
took only about 0.11 seconds across both calls, while loads took 17.67 seconds.
Reasoning was not the dominant measured cost there. The longer document
response did include more reasoning, so that remains workload-dependent.

To repeat manually, restart the updated app, send hi twice in Auto, then twice
with gemma4:e2b selected. Watch the [timing] lines and ollama ps context/process
fields. Compare second turns separately from first loads; record tokens and
load durations, not just total time. A document explanation checks the 12b
route without permitting document changes.

## Verification and scope

The new offline regression first failed with four simulated loads where one
was expected, then passed after the fix. Eight new cases cover context reuse,
logging of every call path, privacy, malformed stats, logging failures,
manual/document routes and unchanged reasoning policy. All 291 offline
assertions in sixteen suites and five native Windows/Tk suites pass.

SCORECARD.md and its empty Results table were not changed or run. This branch
is a performance fix stacked on the existing feature branch; main remains
unmerged. To score main, identify a main checkout and commit first: the
C:/dev/agent/start_chat.bat launcher points at C:/dev/local-ai-agent, which
currently follows the working feature branch rather than main.

Reload behavior reference for the tested version:
https://github.com/ollama/ollama/blob/v0.40.3/server/sched.go#L1310-L1356
