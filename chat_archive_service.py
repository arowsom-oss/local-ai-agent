"""App-lifetime idle ZIP checks. No OS schedule, network, or model-facing tool."""
import threading
import chat_library as saved

INTERVAL_MS=60*60*1000


def report_text(report):
    if report.get('disabled'):return 'Automatic ZIP is disabled. Enable it before checking unused chats.'
    text=(f"ZIP check: {report['archived']} saved chats archived; "
          f"{report['payload_bytes_saved']:,} payload bytes saved; "
          f"{report['disk_bytes_reclaimed']:,} database bytes reclaimed.")
    if report.get('cancelled'):text+=' Check cancelled before replacement.'
    if report.get('compaction_deferred'):text+=' '+report['compaction_deferred']+'.'
    if not report['archived'] and not report['disk_bytes_reclaimed']:
        text+=' Recent, open, tiny or insufficiently compressible chats stay unchanged.'
    return text


def start_maintenance(ui):
    """Only the real app entry point calls this; GUI tests opt in explicitly."""
    if getattr(ui.root,'_archive_service_started',False):return
    ui.root._archive_service_started=True
    active=threading.Event()
    def tick():
        if not ui.root.winfo_exists():return
        # Merely starting the app must not create a library or store a chat.
        if (not ui.busy and not ui.stop_event.is_set() and not active.is_set()
                and (saved.library.root/'library.sqlite3').is_file()):
            active.set()
            exclude=(ui.saved_chat['id'],) if ui.saved_chat else ()
            def work():
                try:
                    report=saved.library.archive_unused(exclude=exclude,
                        cancelled=lambda:ui.busy or ui.stop_event.is_set())
                    if report['archived'] or report['disk_bytes_reclaimed'] or report.get('compaction_deferred'):
                        ui.events.put(('log','[storage] '+report_text(report)))
                except Exception:
                    ui.events.put(('log','[storage] ZIP check unavailable; no automatic retry this hour.'))
                finally:active.clear()
            threading.Thread(target=work,daemon=True).start()
        ui.root.after(INTERVAL_MS,tick)
    ui.root.after(5000,tick)
