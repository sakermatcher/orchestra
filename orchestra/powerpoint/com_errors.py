"""
COM error hierarchy and retry decorator.
"""
from __future__ import annotations
import time
import functools
from orchestra.constants import COM_RETRY_ATTEMPTS, COM_RETRY_DELAY_MS


class COMError(Exception):
    """Base class for all COM-related errors."""
    pass


class COMNotAvailableError(COMError):
    """pywin32 is not installed or PowerPoint is not installed."""
    pass


class COMFatalError(COMError):
    """COM operation failed after all retries. Session must be aborted."""
    pass


class COMThreadError(COMError):
    """Attempt to call COM from wrong thread (RPC_E_WRONG_THREAD)."""
    pass


class PresentationNotOpenError(COMError):
    """Tried to control slides but no presentation is open."""
    pass


def com_retry(max_retries: int = COM_RETRY_ATTEMPTS,
              delay_ms: int = COM_RETRY_DELAY_MS):
    """
    Decorator that retries a COM call on transient failures.
    Raises COMFatalError after max_retries.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except COMFatalError:
                    raise
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        time.sleep(delay_ms / 1000.0)
            raise COMFatalError(f"COM call failed after {max_retries} attempts: {last_exc}") from last_exc
        return wrapper
    return decorator
