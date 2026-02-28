"""
COMWorkerThread — dedicated OS thread for all PowerPoint COM operations.

This module provides the thread class. The thread itself is STARTED in main.py
BEFORE eventlet.monkey_patch() is called, ensuring it gets a real OS thread.

The command queue accepts callables: `command_queue.put(lambda: controller.open(...))`.
"""
from __future__ import annotations
import queue
import threading
from typing import Optional

from orchestra.powerpoint.com_errors import COMFatalError


class COMWorkerThread(threading.Thread):
    """
    Reference implementation for documentation.

    NOTE: In production, the actual thread is created in main.py using
    raw threading.Thread before monkey_patch(). This class documents the
    design but the actual thread runs the _com_thread_entry function defined
    in main.py. The (command_queue, result_queue) pair from main.py is injected
    into the engine via OrchestraApp.

    This class can be used in testing scenarios where you want to isolate COM.
    """

    def __init__(self):
        super().__init__(daemon=True, name="COMWorkerThread")
        self.command_queue: queue.Queue = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self._ready = threading.Event()

    def run(self) -> None:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass
        self._ready.set()

        try:
            while True:
                cmd = self.command_queue.get()
                if cmd is None:
                    break
                try:
                    result = cmd()
                    self.result_queue.put(("ok", result))
                except COMFatalError as e:
                    self.result_queue.put(("fatal", e))
                except Exception as e:
                    self.result_queue.put(("error", e))
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def wait_until_ready(self, timeout: float = 3.0) -> bool:
        return self._ready.wait(timeout=timeout)

    def shutdown(self) -> None:
        self.command_queue.put(None)
        self.join(timeout=2.0)
