# Bounded edits to saved text

document_edit(document, find, replacement) adds a simpler path for small changes.
It cannot create a new document, choose a path or alter existing files in place.
The Artifact/save workflow remains for new documents and broad rewrites.

1. List Documents and read the latest target with document_read(document, 0).
2. For append, use empty find and literal replacement text, including any desired
   leading newline. For replacement, find must match one exact excerpt.
3. Code constructs the complete proposal and a separate document Artifact.
4. Review the same full before/after comparison and exact-save popup.
5. The existing one-use commit verifies state and publishes a fresh version.

Example: after reading Document 3, document_edit(document=3, find="red folder",
replacement="blue folder") changes that exact excerpt once. To append a line,
use find="" and a replacement containing an actual newline followed by the line.
JSON encodes an actual newline as \n. A literal backslash plus n is different
text: the code does not decode escapes or silently repair arguments.

## Code checks

document_read's final JSON line is now an object, such as {"text":"Hello"}.
Its text value is Hello, without JSON delimiter quotes. Quotes inside the actual
value remain document characters. This replaces the earlier bare JSON string;
manual consumers of that result should read its text field. Tool arguments,
metadata line and approval flow are unchanged. A missing find now returns a
specific not-found error, distinct from repeated matches. No unquoting or fuzzy
repair is performed by the edit backend.

Only a successful latest document_read records edit provenance: numbered file
identity, saved version/hash, plus the returned Artifact revision. Historical
reads, Stop, New chat, manual save observations and commits revoke it. Read again
before the next edit. Version/Artifact counters and paths are not model arguments;
extra parameters are refused.

Latest inventory and saved bytes must still match. If the recorded Artifact was
revised, the edit is refused so recorded human/AI draft changes are not silently
discarded. This observes stored revisions; it cannot make the uncommitted GUI
buffer or concurrent human activity atomic. The panel separately retains its
existing protection of unsaved editor text.

Replacement is literal, case-sensitive and exact. Missing, multiple (including
overlapping) matches, no-op edits, invalid controls, empty final text and results
over 8000 characters are refused. No regex, scripts, escape decoding, fuzzy or
global replacement is used.

The proposal uses the existing 120-second one-use approval, full inventory
comparison, native file guards, Stop checks, worker deadline and complete
read-back verification. Save/version/Artifact limits remain. The direct tool
function cannot write outside the approval dispatcher. Plans never approve edits.

Denied, malformed, stale or failed requests end the turn and defer queued actions.
A document Resume fresh-read failure also ends that turn, preventing an automatic
read/retry. A new person request can read current state and review a new proposal.
Uncertain publication appears as Unconfirmed and requires Check last save.

## Verification

19 offline edit tests fake files/model/approvals and block Internet sockets.
They cover literal preservation, overlapping/absent matches, bounds, latest reads,
history, cancel/reset, stored draft changes, limits, actual parameter checks,
exact approval during plans, queued fallback refusal, Stop, frozen proposals,
Resume and uncertain-save recovery. The evaluator also tests its byte oracle
with this tool and additional tasks. New checks distinguish JSON framing from
genuine quoted text, preserve fixed refusal codes without storing draft content,
and prove a human edit actually happened before awarding a stale-control pass.

Real Windows worker fixtures passed append/history, a human change during preview,
refusal without an extra version, and lost confirmation after actual edit
publication followed by independent hash verification. Existing Document/Tk
approval and progress/Resume fixtures passed again. These are implementation
checks; model task results, including failures, are in RELIABILITY.md.
