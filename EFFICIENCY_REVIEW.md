# Efficiency and correctness review - October 20, 2026

Reviewed the request/compaction loop, Ollama manager, Artifacts import/selection/
playback, worker cancellation, generation admission, speech, filesystem workers
and browser interception. Baseline: f1215c9e7e01522a08988d4d589f8a6c399fbd41,
including context reuse. This is a scoped engineering review with reproduced
failures, not proof of zero bugs or a completed security audit.

## Reproduced and fixed

| Trigger | Before | After |
| --- | --- | --- |
| Import image/video | Validation, refresh and explicit selection decoded three times | Reuse validated frames and select once |
| Change selection during decoding | Obsolete work continued and stale pixels could queue | Cancel that preview independently and discard late results |
| Edit text while import validates | Completion could replace the newer unsaved buffer | Add media to the list and preserve newer text |
| Rapid pause/resume | Two timers could advance the same video | Cancel the old timer; retain one playback chain |
| Stop during compaction | A new reply inference could start afterward | Check Stop before the next inference |
| Stop during normal inference | Late content could enter history as a completed reply | Discard late content and tool calls |
| Empty model reply | None could terminate UI polling in the formatter | Explicit error; formatter tolerates missing text |
| Invalid summary | Empty, truncated, action-bearing or oversized output could replace history | Validate first and preserve history on refusal |
| Large historical tool arguments | Omitted from size estimates and summary input | Include tool name/arguments as untrusted data |
| Cancel while waiting for generation admission | Heavy worker could still start | Recheck Stop after GPU lease and RAM check |
| Empty/truncated media interpretation | Could appear and be retained as complete | Error; no incomplete observation in history |

No new tool, dependency, model, persistent cache or listener was added. The
8,192-token context, normal reply thinking, GPU serialization, IP pinning,
download restrictions and exact approvals remain. Per-preview cancellation
targets only its decoder; imported images remain normalized PNGs.

## Native before/after measurement

The same fixture ran on exported unmodified baseline and updated sources in
the existing runtime. Temporary synthetic media: 384x256 JPEG and 65-frame,
24-fps MP4. Real Tk, Pillow, PyAV and bounded decoder processes; no Internet,
inference, microphone or personal file access.

| Observation | Baseline | Updated final run |
| --- | ---: | ---: |
| JPEG decoder jobs | 3 | 1 |
| MP4 decoder jobs | 3 | 1 |
| Maximum simultaneous decoders per import | 2 | 1 |
| JPEG first visible preview | 1.2495 s | 0.6092 s |
| MP4 first visible preview | 1.3627 s | 0.8821 s |
| Timers after rapid pause/resume | 2 | 1 |
| New unsaved text preserved | No | Yes |
| Obsolete preview saw cancellation | No | Yes |

Counts establish removal of duplicate work. Times are individual samples with
process-startup/OS-cache variation, not general speed guarantees. Peak laptop
RAM/VRAM was not measured: decoder counts and Job ceilings do not establish
physical-memory savings. GPU generation settings/quality are unchanged and
were not newly benchmarked. The previous chat A/B remains in PERFORMANCE.md.

## Verification

All twelve new offline cases failed on preserved baseline source and pass on
the updated runtime. They call production functions with fake inference,
workers and approvals, including the actual import request shape. The native
fixture separately reproduced duplicate decoding, unsaved-text loss, duplicate
timers and absent selection cancellation before passing on the updated UI.

All 303 offline cases in 17 suites pass. Six native Windows/Tk suites pass:
Artifacts, selected-media UI, progress, Documents, speech/reference and the new
efficiency fixture. SCORECARD.md is unchanged and remains unrun. Raw local
reports retain both failures and passes; no media or personal audit logs are
uploaded. Run without -O in the existing media-capable environment:

```text
python -B test_efficiency.py
python -B test_efficiency_ui.py
```

The native fixture accepts --report PATH for an exclusive JSON result.
--measure-only records historical failures; normal mode asserts success.

## Remaining efficiency work, in priority order

1. Measure mixed real workflows and the fixed scorecard on an identified
   checkout before considering merges; preserve every failed row. These
   regression results do not establish model accuracy on unseen tasks.
2. Budget tool schemas, system instructions and generation using measured
   prompt counts. History still uses characters/4, not a tokenizer; current-turn
   tool batches cannot always be compacted. Counting omitted arguments fixes
   one failure, not all context exhaustion. Summary quality is model-dependent.
3. Compare load, prompt-evaluation and generation timings across representative
   work. Auto still classifies general requests; model changes intentionally
   unload managed weights. Manual selection remains available. This patch
   does not disable reasoning or approvals for a speed score.
4. Design cancellable model/browser I/O and asynchronous browser shutdown.
   Stop prevents follow-on work but cannot forcibly interrupt an in-flight sync
   Ollama, HTTP or DNS call; New chat may wait for browser cleanup. Avoid
   abandoning owner threads or starting concurrent inference as a shortcut.
5. Profile maximum-size editor formatting, long chat rendering and frame
   display before adding bounded caches or debounce timers. Preserve edits,
   pixel normalization and cancellation in any such change.

Full desktop control and remote authenticated text/media access remain
separate unfinished work. This build remains a supervised prototype.
