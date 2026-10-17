# First real-app adapter: scratch Notepad

Choose Notepad in Local Studio's sidebar, or ask:
"Open scratch Notepad and draft a short paragraph about cells. Do not save a file."
Approve opening the separate scratch window. The model then reads its recorded
document number and requests an exact before/after edit preview. Each edit needs
its own approval, even during a browser plan. No starts focused; Enter, Escape
and closing the approval dialog deny. No changes to the installed agent are
required to try the prepared workspace build.

The three new model tools are:

| Tool | Code permits |
| --- | --- |
| notepad_start() | Request an owned empty classic Notepad after approval |
| notepad_read() | Read only that document, with an untrusted-data prefix and fresh element number |
| notepad_replace(element, text) | Propose exact replacement text; core resolves, asks approval, commits and verifies |

No accepted arguments select a PID, HWND, application, path, URL, file, menu or
keyboard shortcut. There is no Notepad click/open-file/save/print/close tool, no
clipboard or keystroke fallback, and no attachment to existing Notepad windows.
Desktop/practice commands still target only the practice app. Artifacts remain
inert. Existing network, file-read and browser approval rules are unchanged.

## Ownership and document checks

Code derives the system directory from Windows, starts only its installed
notepad.exe with no document argument, verifies the actual executable image,
and requires exactly one visible classic Notepad window containing its expected
native Edit control and a writable UI Automation ValuePattern. The initial value
must be empty. The retained process handle, PID, window/control handles, parent
relationship, root/control runtime IDs and untitled-window title bind the session.
Modern tabbed Notepad and arbitrary applications have no fallback path.

Reads create fresh numbers and invalidate earlier numbers/previews. Code re-reads
state before presenting a proposal and immediately before mutation. Approval is
bound to an opaque one-use token, exact state and text, expiring after 120 seconds.
The token is never supplied to the model or recorded in persistent audit. Edits
use only UI Automation ValuePattern.SetValue on the checked control. After an edit,
code re-observes the same document and compares the full normalized text. It never
blindly retries a mutation. A verification/backend/identity failure halts the
session until the person closes it and starts another approved scratch window.
Ordinary text changes between read/preview and commit are refused as stale.

A process-specific WinEvent hook watches menu and dialog activity before the app
starts and while approval is pending. A menu or dialog event permanently taints
that session, including after it closes. This prevents continued automation after
common document-changing human actions. It is a best-effort application guard,
not an atomic transaction against all possible concurrent human/third-party edits.

## Launch compatibility and lifecycle

On this machine, a normal System32 Notepad launch redirected to the packaged app
and restored existing tabs. Inspection reported only structure/empty-state
metadata; no existing tab was edited or closed. The adapter therefore uses the
installed classic executable, rather than connecting to the packaged process.

The compatibility launch uses CreateProcessW with DEBUG_ONLY_THIS_PROCESS and
CREATE_SUSPENDED, verifies/assigns the newly created process to a kill-on-close
Windows Job, installs its guard, detaches using DebugActiveProcessStop, then
resumes its first thread. No debugger remains attached during editing. This
behavior was tested on this Windows build; it is not a promise that every future
Windows installation retains classic Notepad. Launch failure, an unexpected
executable, unsupported controls or a denied API call fail closed. It never asks
for elevation or changes registry values, security policy or app aliases.
Preconfigured debugger launch rules in either registry view cause refusal;
the check reads only the bounded Notepad launch-policy subtree and never writes it.

Only this new child is briefly created under a debugging relationship; existing
processes are not attached to a debugger. No memory injection, external debugger,
UNC/admin-share launch, downloaded binary or shell is used. Supporting API docs:
[process creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags),
[debugger detach](https://learn.microsoft.com/en-us/windows/win32/debug/debugging-a-running-process),
[UI Automation value operations](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/add-content-to-a-text-box-using-ui-automation),
[process-specific event hooks](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook).

Stop/F12/global Stop, New chat or exiting Local Studio terminate the owned worker
and scratch Notepad, discarding unsaved scratch text. The initial popup explains
this. Keep personal work in your usual editor windows. To keep a result, copy it
into an Artifact and use person-controlled Export, or save manually in Notepad.
Using menus/dialogs to save manually ends automation for that session. The agent
never invokes a document-save operation. A manually saved file is not deleted.
This is real Notepad under normal user privileges, not an OS sandbox or a promise
that the application/OS writes no settings, logs, paging or crash data.

## Fixed bounds

- 2,000 text characters, also bounded to 2,000 UTF-16 code units; printable text
  plus tabs/newlines. The native control's text-length check may impose a stricter
  bound for newline representations. Read-back normalizes CRLF to LF.
- 1,000 reads and 50 edits per session. Numbers are not reused across restarts.
- 120-second proposal expiry; 15-second command/start waits. The startup window
  wait is at most 8 seconds. Verification re-observes up to 20 times, never
  reapplying the action. Stop can terminate a blocked COM worker through its Job.
- Owned worker Job commit limit 768 MB; a separate child Job bounds classic
  Notepad to 256 MB and kills it when the worker's handle closes. These are
  memory/lifecycle limits, not least-privilege or network isolation.

## Validation

14 offline plain-assert tests cover strict arguments, no arbitrary app/file/save
capability, initial empty-state refusal, stale reads, changed target/text, expired
and replayed tokens, verification failure without retry, callback mutation,
mandatory per-edit approval during plans, launch denial, Stop during approval,
text/UTF-16 budgets, read/action budgets and fresh session numbering.

Real classic Notepad tests passed empty launch, UIA reads and two successive
edits from different caller threads, replay/stale refusal, human change after
preview, and termination of only the owned worker and scratch process. A real
File-menu event halted the session permanently; closing that menu did not resume
it. Real Tk checks covered both Notepad approval dialogs: No focused/visible,
Enter/Escape denied, explicit Yes approved. None of these fixtures saved a file.

Actual local gemma4:e2b completed start/read/approved replacement with exactly
SYNTHETIC NOTEPAD CHECK in 15.57 seconds. Test approval callbacks allowed only
that synthetic scratch operation and are not installed in production UI. This
single run does not establish general model reliability or absence of bugs.
