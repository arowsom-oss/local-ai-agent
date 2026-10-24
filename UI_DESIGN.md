# A calmer Local Studio

This pass follows Alexander's request for fewer interruptions, uniform panels and
an original AI icon. Apple's Human Interface Guidelines informed the hierarchy,
spacing and restraint; this remains a native Windows/Tk app with Segoe UI.
It does not copy Apple branding, fonts or glass effects.

Design references: [Layout](https://developer.apple.com/design/human-interface-guidelines/layout),
[Modality](https://developer.apple.com/design/human-interface-guidelines/modality),
[Alerts](https://developer.apple.com/design/human-interface-guidelines/alerts).

- Conversation first: tool/timing logs go to **More > Activity**, not the chat.
  Blocked actions and errors remain visible. Activity keeps the latest 100
  bounded entries in RAM and clears on New chat; it does not change saved audit
  redaction or the model's tool results.
- One utility panel at a time: Activity, Documents, task details and Edge panels
  share a close footer. Opening another closes the previous utility view.
  Closing a view does not erase a draft, undo a completed action or disconnect an
  already paired personal tab. Use Disconnect or Stop to revoke that connection.
- Neutral light/dark surfaces, a single blue accent, shared type and spacing.
  Technical browser plumbing moved to documentation; exact destinations, text
  changes and website effects remain in required approval previews.
- The original generated icon is bundled in assets/ as RGBA PNG and nine-size
  Windows ICO. The app sets its window icon and Windows application identity.
  See [asset provenance and the exact generation prompt](assets/README.md).

## Popup inventory and close behavior

| Surface | Close/cancel behavior |
| --- | --- |
| Exact action approvals, plans, searches, saves, generation | No, Escape, Return or X deny; explicit Yes is required |
| Image/reference-photo preview | No, Escape, Return or X reject the image |
| New chat, capture/model check, discard edits | Cancellable app prompt; No, Escape, Return and X leave the action undone |
| Edge setup | Close, Escape, X; successful Start/Choose also close setup |
| Edge tab picker | Cancel, Escape, X; long lists scroll; empty lists still have Cancel |
| Pairing-code display | Close code window, Escape, X hide the code; sharing is separately disconnected |
| Activity and saved audit | Close, Escape, X; bounded text, no tool execution |
| Task details | Close, Escape, X; does not resume a task |
| Saved Documents | Close, Escape, X; no deletion; late listing results ignore a closed view |
| Optional Edge connector popup | Close connector or Escape revoke sharing then close; title-bar closure expires via heartbeat |
| Native Open/Save and text prompt | Native Cancel/X/Escape; explicit parent keeps dialogs attached to the app |
| Model, Artifact and version lists | Escape dismisses without stopping the session |

Footer space is reserved before expanding content. Windows monitor work areas
bound popup placement; small work areas and negative-coordinate geometry have
tests. Modal grabs are released even when a callback fails, and an enclosing
modal is restored. Normal panels do not become modal just to display information.
Native menu cancellation uses the platform's existing behavior; synthetic Tk
events did not reliably drive the Windows menu loop in the fixture. This is not
claimed as a successful native-menu automation test or every-monitor guarantee.

## Launcher icon

Use the **Local Studio** shortcut instead of double-clicking a Python source file.
Its icon points at the bundled ICO. Windows' Python file association is unchanged.
To make a shortcut on another clone, run scripts/create_shortcut.ps1 with the
existing app runtime's pythonw.exe via -Pythonw; no model/runtime download occurs.
An unrelated existing shortcut is preserved rather than overwritten.

## Verification and limits

363 cases in 20 offline suites pass. Nine affected native suites pass after the
visual changes, including real Open/Save cancellation, all nine custom dialog
types, unsent-draft protection, nested grabs, live panel replacement, Activity and
the actual Windows icon/process identity. The extension fixture checks its own
popup Close/Escape revocation. Light/dark UI previews use only synthetic content.

The earlier broad run passed 11/12 native suites: a global shortcut registration
was unavailable while another process held it. The remaining desktop hard-stop
and owned practice UIA cases passed separately. That failure remains in evidence;
no running personal/app process was stopped to free the shortcut. Native-menu
and icon-getter fixture assumptions were corrected with retained logs. No human
main scorecard, live model quality test or full Windows security audit is claimed.

## Saved chats/Projects utility

The sidebar has Chats & Projects. Its content scrolls while status and Close
remain fixed; Escape/X dismiss it. The Project editor also has Close/Escape/X.
Save controls name the opened saved target independently of list selection.
Delete/Open/Project removal keep No-default confirmations. Lists, entries and
Project text share the palette. Closing a pending Open discards it; a committed
Save can still finish and update its saved metadata without reopening the view.

## Saved snapshot ZIP controls

Chats & Projects adds a Storage (Plain/ZIP) column and a themed Auto ZIP checkbox
with Check unused chats now. Existing scrolling/fixed Close/status remain.
The toggle persists locally, defaults on and leaves archived snapshots readable
when off. No additional approval popup or model action is added. Actual status
separates payload bytes saved from database bytes reclaimed; disabled/deferred
checks explain why. AUTO_ARCHIVE.md has the seven-day scope and native evidence.

## Sources Q&A

One themed utility window adds explicit sources, a bounded question, answer and
an inspectable citation/extracted-text view. Main model selection applies; all
listed sources are in scope. The fixed Close/status footer stays visible while
the body scrolls. Close/Escape/X cancels pending work; late results never reopen
or replace data. It retains selected snapshots until explicit Forget/New chat.
Read-only result panes never render links/code. Keep answer creates a fresh
Artifact without dropping a dirty editor. There are no per-question approval
popups, action tools or persistent-source authorization grants. DOCUMENT_QA.md
records privacy and the fact that quote matching is not factual entailment.
