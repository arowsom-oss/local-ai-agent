# Task progress and safe resume

Local Studio now shows a compact Task progress panel in the conversation pane.
Details opens a live action history and the model's proposed steps. These are
RAM-only records for the current task, not a persistent job scheduler.

## What each status means

- Proposed steps are bounded model text, explicitly labeled unverified. The
  optional outline_task tool accepts 1 to 8 printable descriptions, each at most
  120 characters. It grants no permission and cannot mark a step complete.
- Requested, Awaiting approval, Approved and Denied describe the permission flow.
  Approval alone is not proof that an action happened.
- Observed means a read tool returned successfully. It does not certify that the
  text is true or that media interpretation is correct.
- Verified is reserved for explicit successful Notepad/practice read-back,
  saved-document verification and code-confirmed in-memory Artifact creation or
  revision. A count includes those individual operations, not just disk saves.
- Returned means a tool returned a status without one of these explicit
  verification contracts. It does not count as a verified task result.
- Refused and Deferred show blocked requests and queued actions that were not run.
- Reply ready means the model produced a reply. It never means the whole user
  goal was independently verified. Only trusted core outcomes determine Paused,
  Failed and Stopped; model reply text cannot forge those states either.

Plans and actual action history are displayed separately. Free-form proposed
steps are not automatically matched to tool calls or checked off. There is no
invented completion percentage. A corrected request can clear an unresolved
refusal while the earlier refusal remains visible in history.

## Checkpoints and Resume

A paused, failed or stopped text task can offer Resume. Clicking it starts a new
turn for the original person request, with a fresh evidence scope. It does not
replay saved tool calls, tokens, decisions or planned browser-step indices.
Read permission already granted for the chat remains scoped to that chat; exact
mutation/outbound approvals are still handled by their existing gates.

On a resumed turn, code requires an actual successful current read before:

- numbered browser clicks/searches;
- Notepad replacements and practice mutations;
- revising an existing Artifact, unless it was created in this resumed turn;
- saving an Artifact or updating an existing saved document. The latter also
  requires a new document_read for that document.

Normal backend identity, revision, state, token and read-back checks still apply.
A mutation consumes the corresponding observation. A fresh launch/navigation
invalidates the previous app/page observation. Failed reads do not unlock edits.
A closed or permanently halted app can still require a fresh approved start.
Resume does not bypass this or guarantee that the model can recover unaided.

The UI preserves verified history/counts while starting a new scoped turn. Stop
and New chat ignore late results from the old serial. New chat clears all task
records. An unsent composer message is preserved rather than overwritten by
Resume. Selected-media turns and requests longer than 4,000 characters do not
store a resumable request; reattach media or send a new instruction instead.
The visible action history retains the most recent 100 entries. Counters can
include earlier entries. Nothing in this feature writes checkpoints to disk.

The model/tool loop is now bounded to seven responses rather than five, to allow
an outline and a fresh read during recovery. It still pauses at the bound and
never continues automatically in the background.

## Implementation and privacy

agent_core.py emits structured events at trusted dispatch, approval, result and
return boundaries. It never parses chat logs or model final answers as completion
evidence. Browser/document text cannot forge a different tool's verified result.
Verification records an operation at that time; it is not continuous monitoring
of the current window or file after a person or another program changes it.
The worker updates a locked RAM tracker; only Tk's thread renders widgets.
Progress-display callback failures do not alter approvals, execute extra actions
or repeat a mutation.

The checkpoint holds the original person request, proposed labels and bounded
metadata history, not full tool payloads, screenshots, file bytes or approval
tokens. Chat and tool results retain their existing handling. A proposed step
could still quote sensitive text; the panel is not a redaction filter.

Saved-document errors were clarified during testing: an existing document needs
the positive saved version returned by document_read, and Artifact revisions
must be current. Metadata/warning lines are not document contents. These help
messages do not relax either check.

## Validation and limits

17 offline plain-assert cases prohibit Internet sockets and use fake models,
apps and approvals. They cover forged completion/failure text, read data shaped
like receipts, unverified outlines, separate approvals, denial, current-read
requirements, history/counter bounds, correction of refused requests, callback
failure, Stop, old serials, reset and checkpoint lifetime.

The real Tk fixture used synthetic model and Notepad backends. It passed a
refused edit, a simulated human change, Resume invoking a fresh read and separate
exact approval, verified-result display, a visible Resume control, Stop and New
chat. The existing Tk approval, Artifacts and Windows/Documents suites passed
again. Compact and detail panel screenshots were visually inspected.

A final local gemma4:e2b exact-text fixture passed in 22.03 seconds: the first save
was refused for a stale Artifact reference; after a synthetic human edit, Resume
read the current saved document and obtained a new exact-save approval. Version 2
matched the requested replacement and version 1 remained. The tracker ended at
Reply ready, with two observations and three verified operations including RAM
Artifact revisions. Test callbacks only allowed the fixed synthetic text in a
temporary folder; they are never part of production UI.

This successful run followed three guarded unsuccessful attempts: saved-version
confusion, unwanted metadata in a free-form draft, and recovery exhausting the
previous five-response limit. No unapproved document update occurred. A simpler
exact-text task passed after clearer tool help and the bounded seven-response
budget. Open-ended recovery reliability remains unproven. The panel reports code
evidence; it does not solve model planning or certify an entire task's correctness.
