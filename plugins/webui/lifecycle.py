"""Track the authenticated browser connection that owns a WebUI process."""

import threading

BROWSER_LIFECYCLE_GRACE_PERIOD = 1.5


class BrowserLifecycle(object):
    def __init__(self, on_empty, grace_period=BROWSER_LIFECYCLE_GRACE_PERIOD):
        self._on_empty = on_empty
        self._grace_period = grace_period
        self._lock = threading.Lock()
        self._connections = set()
        self._timer = None
        self._closed = threading.Event()
        self._shutdown_requested = False

    def connect(self):
        token = object()
        with self._lock:
            if self._closed.is_set() or self._shutdown_requested:
                return None
            self._connections.add(token)
            self._cancel_timer_locked()
        return token

    def disconnect(self, token):
        if token is None:
            return
        with self._lock:
            self._connections.discard(token)
            if self._connections or self._closed.is_set() or self._shutdown_requested:
                return
            self._timer = threading.Timer(self._grace_period, self._shutdown_if_empty)
            self._timer.daemon = True
            self._timer.start()

    def close(self):
        self._closed.set()
        with self._lock:
            self._cancel_timer_locked()

    def wait(self, timeout):
        return self._closed.wait(timeout)

    def _cancel_timer_locked(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _shutdown_if_empty(self):
        with self._lock:
            self._timer = None
            if self._connections or self._closed.is_set() or self._shutdown_requested:
                return
            self._shutdown_requested = True
        self._on_empty()
