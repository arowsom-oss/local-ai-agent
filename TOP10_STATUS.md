# Ten improvements: delivered first version

| Priority | Implemented | Scope / remaining work |
| --- | --- | --- |
| 1. Practice environment | Owned native Windows app, RAM-only drafts, clear and undo | Disposable state; not a VM or OS sandbox |
| 2. Semantic observation | Windows UI Automation reads text and numbered controls | Owned practice app only; no OCR coordinate guessing |
| 3. Narrow actions | Set draft value; invoke Save/Clear/Undo | No arbitrary app/PID/HWND/coordinates; 500-character text cap |
| 4. Emergency Stop | Worker Job Objects, Stop, F12, Ctrl+Alt+F9 | Kills owned desktop/media/generation trees; browser/Ollama calls may finish |
| 5. Exact previews | Own No-default popup for every desktop change and generation | Before/after values; one-use token, TTL and state recheck; plans cannot cover it |
| 6. Verify and recover | Re-observe after each action, no blind retry, halt on verification failure | One-level practice undo; not general rollback for real applications |
| 7. Capture/privacy | Owned-window-only capture; actual pixel hide/crop; redacted new audit entries | Person-selected images still require review; old logs unchanged |
| 8. Evaluated routing | Fixed synthetic model check, timings, follow-up retention policy | 7/8 tiny-suite matches; no broad accuracy claim or expert streaming |
| 9. Selected media | English WAV transcription and timestamped MP4 frame contact sheets | 60 seconds / 64 MB; four frames; MP4 audio and between-frame events not analyzed |
| 10. Local generation | Approved SD-Turbo PNG and experimental ModelScope short MP4 | Fixed resolution/steps, CUDA, local weights, unique outputs, process/time/size bounds |

Each item is an initial implementation, not unrestricted computer use. Extending
an app target requires a separate adapter with a reviewed action/verification
contract. No current tool can grant itself a broader scope.

## Additional real-app adapter

A separate, approved classic Notepad scratch process now supports semantic reads
and preview-bound text replacement with read-back verification. It cannot attach
to existing windows or expose file/menu/keyboard commands. This does not broaden
the practice app's tools or grant general desktop control. See NOTEPAD.md.

## Task progress and checkpoints

A compact status and detailed action history distinguish model outlines, reads,
approvals and verified operations. Paused tasks can be explicitly resumed with
fresh-read gates; checkpoints do not replay old approvals or survive New chat.
The panel does not certify whole-task completion. See TASK_PROGRESS.md.

## Saved document workspace

document_edit adds literal appends and unique-excerpt replacements with code-held
read provenance and revision bookkeeping. It retains exact approval, fresh reads,
guarded version publication and uncertainty recovery. Auto has a bounded English
document-workflow routing hint to 12b, following measured model differences.
Independent task/control results and all failures are retained in RELIABILITY.md;
the running project record now includes the evaluation and these improvements.

Document work now uses short-lived owned filesystem processes and an asynchronous
UI, with Stop, a transaction deadline and last-save hash reconciliation after an
uncertain result. New saves cannot bypass that uncertainty check. Friendly titles
and text comparisons improve the existing review flow. A standalone workflow
evaluator records actual model task outcomes, including failures. See
FILESYSTEM_WORKERS.md.

Plain-text document Artifacts can now be saved to a fixed local folder after an
exact approval, with fresh version files instead of overwriting existing text.
The Documents view loads saved history for review and recovery. Folder permission
expires at New chat; saved files remain. No model-selected paths, general file
editing, Word automation or code execution are added. See DOCUMENTS.md.
