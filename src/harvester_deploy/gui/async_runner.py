"""Run asyncio coroutines on a dedicated Qt background thread."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal


class AsyncLoopThread(QThread):
    """Background thread hosting a single asyncio event loop."""

    def __init__(self) -> None:
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = False

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready = True
        self._loop.run_forever()

    def run_coro(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Future[Any]:
        if self._loop is None or not self._ready:
            raise RuntimeError("Async loop not started yet")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def shutdown(self) -> None:
        if self._loop is None:
            self.quit()
            self.wait(5000)
            return

        def _stop() -> None:
            for task in asyncio.all_tasks(self._loop):
                if not task.done():
                    task.cancel()
            self._loop.stop()

        self._loop.call_soon_threadsafe(_stop)
        self.quit()
        self.wait(10000)


class AsyncTaskBridge(QObject):
    """Submit work to AsyncLoopThread; deliver results on the GUI thread via signals."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, loop_thread: AsyncLoopThread, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loop_thread = loop_thread

    def submit(self, coro: Coroutine[Any, Any, Any]) -> None:
        try:
            future = self._loop_thread.run_coro(coro)
        except RuntimeError as exc:
            self.failed.emit(str(exc))
            return

        def _done(fut: asyncio.Future[Any]) -> None:
            try:
                self.succeeded.emit(fut.result())
            except asyncio.CancelledError:
                self.failed.emit("Operation cancelled")
            except Exception as exc:
                self.failed.emit(str(exc))

        future.add_done_callback(_done)
