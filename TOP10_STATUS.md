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
