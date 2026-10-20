# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from collections import deque
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal


class _Worker(QObject):
    finished = Signal(object)
    error = Signal(Exception)
    progress = Signal(object)

    def __init__(self, work_fn: Callable[[Callable[[Any], None]], Any]):
        super().__init__()
        self._work_fn = work_fn


    def run(self):
        try:
            result = self._work_fn(self.progress.emit)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)


# Runs submitted work on a background QThread so the Qt event loop never
# blocks. Only one task runs at a time per queue; further submit() calls
# queue up and run FIFO once the current task finishes.
#
# work_fn is called with report_progress, a function safe to call from the
# background thread to deliver a payload to on_progress on the main thread
# (Qt signal/slot delivery across threads is queued automatically).
#
# Must be a QObject (not a plain class): Qt only auto-queues a
# signal/slot connection across threads when it can see the receiving
# slot's thread affinity, which it can't for a plain function/lambda -
# without this, finished/error handlers below would run on the worker
# thread itself instead of being marshalled back to this queue's thread.
class AsyncTaskQueue(QObject):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pending = deque()
        self._busy = False
        self._thread: Optional[QThread] = None
        self._worker: Optional[_Worker] = None
        self._on_success: Optional[Callable[[Any], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None


    def submit(
        self,
        work_fn: Callable[[Callable[[Any], None]], Any],
        on_success: Callable[[Any], None],
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[Any], None]] = None,
    ):
        self._pending.append((work_fn, on_success, on_error, on_progress))
        if not self._busy:
            self._start_next()


    def _start_next(self):
        if not self._pending:
            self._busy = False
            return

        self._busy = True
        work_fn, self._on_success, self._on_error, on_progress = self._pending.popleft()

        self._thread = QThread(self)
        self._worker = _Worker(work_fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        if on_progress:
            self._worker.progress.connect(on_progress)

        self._worker.finished.connect(self._handle_finished)
        self._worker.error.connect(self._handle_error)

        self._thread.start()


    def _handle_finished(self, result):
        self._cleanup_thread()
        on_success = self._on_success
        on_success(result)
        self._start_next()


    def _handle_error(self, exc):
        self._cleanup_thread()
        on_error = self._on_error
        if on_error:
            on_error(exc)
        self._start_next()


    # quit()+wait() must happen here, synchronously, rather than via a
    # separate finished/error -> thread.quit() connection: that connection
    # would be queued behind this same handler, and wait() would then block
    # the very event loop that needs to run to deliver the queued quit().
    def _cleanup_thread(self):
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
