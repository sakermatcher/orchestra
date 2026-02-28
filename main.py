# Orchestra — Entry Point
#
# IMPORT ORDER IS NON-NEGOTIABLE:
#
#   1. eventlet.monkey_patch()  <- must be the first executable line
#   2. COMWorkerThread start    <- uses original (pre-patch) threading
#   3. Everything else          <- PyQt6, Flask, orchestra modules
#
# eventlet.monkey_patch(os=False) replaces Python's socket, ssl, select,
# and threading with cooperative green-thread equivalents.
# PyQt6's internal C++ threads do NOT use Python threading -- they are safe.
# The COM worker MUST be a real OS thread, so we use eventlet.patcher.original
# to get the un-patched threading and queue modules AFTER monkey_patch.

import eventlet
eventlet.monkey_patch(os=False)  # MUST remain the first executable import

# ---------------------------------------------------------------------------
# COM worker thread — uses the ORIGINAL (pre-patch) threading and queue so
# that the COM thread is a genuine OS thread and its queue is OS-level.
# ---------------------------------------------------------------------------
from eventlet.patcher import original as _ep_original
_real_threading = _ep_original("threading")
_real_queue     = _ep_original("queue")

_com_command_queue = _real_queue.Queue()
_com_result_queue  = _real_queue.Queue()
_com_thread_ready  = _real_threading.Event()


def _com_thread_entry():
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        pass  # pywin32 not installed -- COM unavailable (tests can still run)
    _com_thread_ready.set()

    try:
        while True:
            cmd = _com_command_queue.get()
            if cmd is None:  # shutdown sentinel
                break
            try:
                result = cmd()
                _com_result_queue.put(("ok", result))
            except Exception as e:
                _com_result_queue.put(("error", e))
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


_com_thread = _real_threading.Thread(
    target=_com_thread_entry,
    name="COMWorkerThread",
    daemon=True,
)
_com_thread.start()
_com_thread_ready.wait(timeout=3.0)

# ---------------------------------------------------------------------------
# Now it is safe to import everything else.
# ---------------------------------------------------------------------------
import sys
from orchestra.ui.app import OrchestraApp


def main():
    app = OrchestraApp(sys.argv, com_worker=(_com_command_queue, _com_result_queue))
    exit_code = app.run()

    # Signal COM thread to shut down cleanly
    _com_command_queue.put(None)
    _com_thread.join(timeout=2.0)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
