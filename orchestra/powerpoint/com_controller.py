"""
PowerPointController — thin wrapper around the win32com PowerPoint API.

ALL methods in this class must be called from the COMWorkerThread only.
The constructor asserts the calling thread name as a safety check.

Static convenience methods are provided for use from the COM command queue
(lambdas can't refer to an instance if the instance isn't passed as an argument,
but since the command queue just calls callables, we use class-level state).
"""
from __future__ import annotations
import threading
from typing import Optional
from orchestra.powerpoint.com_errors import (
    COMNotAvailableError, COMFatalError, PresentationNotOpenError, com_retry
)

try:
    import win32com.client
    import pythoncom
    from pywintypes import com_error
    _COM_AVAILABLE = True
except ImportError:
    _COM_AVAILABLE = False
    com_error = Exception


class PowerPointController:
    """
    Singleton-like COM state holder. One instance per session.
    Accessed via static/class-level methods from the COM command queue.
    """

    _instance: Optional["PowerPointController"] = None

    def __init__(self):
        if not _COM_AVAILABLE:
            raise COMNotAvailableError(
                "pywin32 is not installed. PowerPoint control is unavailable."
            )
        _assert_com_thread()
        self._application = None
        self._presentation = None
        self._slideshow_window = None
        PowerPointController._instance = self

    # ------------------------------------------------------------------
    # Static entry points (called via COM command queue)
    # ------------------------------------------------------------------

    @classmethod
    def static_open(cls, filepath: str) -> None:
        if cls._instance is None:
            cls._instance = cls()
        cls._instance.open_presentation(filepath)

    @classmethod
    def static_goto_slide(cls, slide_number: int) -> None:
        if cls._instance is None:
            raise PresentationNotOpenError("No presentation is open.")
        cls._instance.goto_slide(slide_number)

    @classmethod
    def static_close(cls) -> None:
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    @com_retry()
    def open_presentation(self, filepath: str) -> None:
        _assert_com_thread()
        # Close any existing slideshow and presentation from a previous session
        # so that restarting a session works without quitting and relaunching.
        if self._slideshow_window is not None:
            try:
                self._slideshow_window.View.Exit()
            except Exception:
                pass
            self._slideshow_window = None
        if self._presentation is not None:
            try:
                self._presentation.Close()
            except Exception:
                pass
            self._presentation = None

        if self._application is None:
            self._application = win32com.client.Dispatch("PowerPoint.Application")
            self._application.Visible = True

        self._presentation = self._application.Presentations.Open(
            filepath, ReadOnly=False, Untitled=False, WithWindow=True
        )
        version = float(self._application.Version)
        print(f"[COM] Opened presentation. PowerPoint version: {version}")

    @com_retry()
    def start_slideshow(self) -> None:
        _assert_com_thread()
        if self._presentation is None:
            raise PresentationNotOpenError("No presentation open.")
        settings = self._presentation.SlideShowSettings
        settings.ShowType = 1  # ppShowTypeSpeaker — full screen
        self._slideshow_window = settings.Run()
        print("[COM] Slideshow started.")

    @com_retry()
    def goto_slide(self, slide_number: int) -> None:
        _assert_com_thread()
        if self._slideshow_window is None:
            # Try starting if not started
            self.start_slideshow()
        try:
            self._slideshow_window.View.GotoSlide(int(slide_number))
        except com_error as e:
            raise COMFatalError(f"GotoSlide({slide_number}) failed: {e}") from e

    @com_retry()
    def get_current_slide(self) -> int:
        _assert_com_thread()
        if self._slideshow_window is None:
            return 1
        try:
            return self._slideshow_window.View.CurrentShowPosition
        except com_error:
            return 1

    @com_retry()
    def get_slide_count(self) -> int:
        _assert_com_thread()
        if self._presentation is None:
            raise PresentationNotOpenError("No presentation open.")
        return self._presentation.Slides.Count

    def close(self) -> None:
        _assert_com_thread()
        try:
            if self._slideshow_window:
                try:
                    self._slideshow_window.View.Exit()
                except Exception:
                    pass
                self._slideshow_window = None
            if self._presentation:
                try:
                    self._presentation.Close()
                except Exception:
                    pass
                self._presentation = None
        except Exception:
            pass
        # Do NOT call Application.Quit — user may have other presentations open


def _assert_com_thread() -> None:
    name = threading.current_thread().name
    if name != "COMWorkerThread":
        from orchestra.powerpoint.com_errors import COMThreadError
        raise COMThreadError(
            f"COM method called from wrong thread: {name!r}. "
            "All COM calls must be made from COMWorkerThread."
        )


def get_slide_count_no_com(filepath: str) -> int:
    """
    Get slide count without opening the presentation via COM.
    Uses python-pptx as a fallback (does not require PowerPoint to be installed).
    """
    try:
        from pptx import Presentation
        prs = Presentation(filepath)
        return len(prs.slides)
    except Exception:
        return 0
