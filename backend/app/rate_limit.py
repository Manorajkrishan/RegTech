"""Per-process, socket-IP auth throttling. Production also needs shared edge limits."""
from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

_lock = Lock()
_windows: dict[tuple[str, str], deque[float]] = {}
LIMITS = {"login": (15, 60), "register": (20, 3600), "password_email": (10, 3600)}


def throttle(request: Request, purpose: str) -> None:
    limit, seconds = LIMITS[purpose]
    peer = request.client.host if request.client else "unknown"
    key = (purpose, peer)
    now = monotonic()
    with _lock:
        if len(_windows) > 20_000:
            for candidate in list(_windows):
                if not _windows[candidate] or now - _windows[candidate][-1] > 3600:
                    del _windows[candidate]
        window = _windows.setdefault(key, deque())
        while window and now - window[0] >= seconds:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please retry later.",
                headers={"Retry-After": str(max(1, int(seconds - (now - window[0]))))},
            )
        window.append(now)


def reset_for_tests():
    with _lock:
        _windows.clear()
