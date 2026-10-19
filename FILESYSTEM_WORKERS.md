# Filesystem workers and save recovery

Document filesystem work now runs in short-lived owned Windows processes, with
one transaction per worker. Listing, reading, preview preparation, observation,
publishing and recovery keep their existing fixed-folder checks. No model tool
accepts a path, command, worker target or timeout.

## Responsive operations and Stop

Each transaction has a ten-second deadline shared by worker startup replies and
its command/reply waits. The worker is assigned to a 256 MB Windows Job. Normal
completion closes the Job; deadline, disconnect and Stop terminate it. Native
file handles and directory pins live in that process. They are retained across
read/compare/publish commands within the same transaction, so isolation does not
weaken the existing no-reparse, no-hard-link, state or no-overwrite checks.

Document UI operations run on background threads and return through a queue to
Tk. A manual document operation enables Stop even while no model turn is active.
Cancel does not wait for the operation lock held by disk work. Generation checks
prevent a late read from restoring an observation or Artifact after New chat.
New chat forgets workspace access and target numbers. Closing a Documents window
does not itself approve, retry or redirect an operation.

Ten seconds is a transaction budget, not a guarantee about every Windows kernel
call or process-creation/termination delay. Compound UI operations can use more
than one transaction, with their own deadlines, plus person approval time. The
window remains responsive while waiting. This is process containment and
cancellation, not a least-privilege OS sandbox or a power-loss durability promise.

## Save outcomes

Code consumes an approval before worker startup. A failed startup therefore
cannot leave a reusable save token. Each dispatched save attempt charges the
per-chat 20-attempt budget. Before publication, trusted parent code records only
the generated file identity, version, expected SHA256 and status in RAM.

A lost reply or Stop around publication reports an uncertain save. Task history
uses Unconfirmed, rather than claiming either a verified save or a refused write.
Preparing another save is blocked while this status remains uncertain. Resume
also directs the person to check first; it does not repeat the old write.

Open Documents and choose Check last save. This is a person-controlled bounded
read, not a new model tool. It checks the one expected generated file using the
same native path/link guards and compares its full bytes with the expected hash.
It does not need to read every other document or repair anything.

- Verified means that expected file matched when checked.
- Different content means the file exists but its bytes differ; review it.
- Not present when checked describes that observation, not a future guarantee.
- Unavailable/timeout leaves the outcome unconfirmed and keeps new saves blocked.

Checking never rewrites or deletes a file and never automatically retries. Old
saved versions remain. The recovery receipt survives Stop and New chat within
this running app, while read permission must be renewed after New chat. It holds
no document text or approval token. App exit loses this RAM-only receipt; inspect
the fixed folder after an interrupted restart. Ignored pending files can remain
when a worker is killed and still count toward the existing directory limit.

## Improvements to existing documents

Documents now displays the first nonempty line as a friendly label, bounded to
80 printable characters. Listing for the model labels those titles as untrusted
data. Code still resolves numbered records to generated UUID/version filenames;
a title never becomes a path or permission. Labels update when current text
changes and do not create a separate metadata file.

Save previews now include a bounded unified text comparison before the complete
before/after JSON text. A shortened comparison is marked; the complete approved
text remains visible. Newer unsaved editor changes are preserved if a load
finishes later. Existing drafts, browser gates, per-edit approval, document
version history and model restrictions remain in place.

## Repeatable task evaluation

Run the standalone evaluator from the prepared runtime:

    python -B evaluate_workflows.py

An optional --output new-report.json writes a new report only, refusing an
existing filename. The evaluator uses synthetic prompts, a new temporary
workspace, a restricted dispatch table and exact-content fixture approvals. It
cannot approve another app, website or arbitrary output path. Such callbacks are
never installed in production UI. It checks actual saved bytes/version counts,
not a model's claim of completion, and stops dependent cases after a failure.

The three fixed cases are new-document creation, exact revision, and a synthetic
human edit after preview that must make the approved save stale. The first strict
run completed only case 1: it failed, with no saved document and one approval
refusal in 13.56 seconds. Cases 2 and 3 were not attempted. This result is retained
in the development evidence rather than retried until it passes.

A separate two-turn local gemma4:e2b create/read/revise smoke run passed with the
real filesystem workers in 25.53 seconds, retaining version 1. Together these
show that task success varies with the request/model output. They do not
establish general reliability. Permission and content checks still need to act
when a model proposal is wrong.

## Validation

Twelve new offline plain-assert cases block Internet sockets and fake disk,
transport, model and approval behavior. They cover shared deadlines, nonblocking
cancel, stale late reads, consumed approvals on startup failure, lost receipts,
unchanged reconciliation, missing/different/unavailable outputs, renewal of
permission, bounded comparisons, Unconfirmed task status and the evaluator
rejecting unsupported approvals and unverified completion claims.

Real Windows fixtures passed worker deadline/termination, cancellation while a
request was blocked, lost confirmation after actual publication, retained prior
versions, independent hash reconciliation, missing outputs and friendly titles.
A real Tk fixture kept its heartbeat alive during a blocked worker, enabled Stop,
cancelled promptly, avoided late writes, checked recovery after Stop, then saved
and listed a document through actual workers. Earlier Windows/Tk fixtures and
all 197 offline assertions passed. Only owned temporary folders were changed by
these tests. No Internet or private documents were used by these fixtures.
