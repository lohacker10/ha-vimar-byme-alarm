"""Passive TCP listener for Vimar 01946 event notifications.

The listener never sends application data. Incoming traffic is used only as a
hint that something changed; Home Assistant then refreshes state through the
Web Server database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import socket
import threading
import time
from typing import Callable


@dataclass(slots=True)
class VimarTcpStats:
    connected: bool = False
    bytes_received: int = 0
    chunks_received: int = 0
    reconnects: int = 0
    last_event_at: str | None = None
    last_error: str | None = None


class VimarTcpListener:
    """Receive-only listener on the Vimar event socket."""

    def __init__(
        self,
        host: str,
        port: int,
        on_data: Callable[[], None],
    ) -> None:
        self.host = host
        self.port = port
        self.on_data = on_data
        self.stats = VimarTcpStats()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket_lock = threading.Lock()
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="vimar-alarm-tcp",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._socket_lock:
            sock = self._socket
            self._socket = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        backoff = 1.0
        had_connection = False
        while not self._stop.is_set():
            try:
                sock = socket.create_connection((self.host, self.port), timeout=5)
                sock.settimeout(1.0)
                with self._socket_lock:
                    self._socket = sock
                self.stats.connected = True
                self.stats.last_error = None
                if had_connection:
                    self.stats.reconnects += 1
                had_connection = True
                backoff = 1.0

                while not self._stop.is_set():
                    try:
                        data = sock.recv(4096)  # Receive only: deliberately no send().
                    except socket.timeout:
                        continue
                    if not data:
                        raise ConnectionError("Vimar TCP socket closed")
                    self.stats.bytes_received += len(data)
                    self.stats.chunks_received += 1
                    self.stats.last_event_at = datetime.now(timezone.utc).isoformat()
                    self.on_data()
            except Exception as err:  # Listener failure must never break polling.
                self.stats.connected = False
                self.stats.last_error = f"{type(err).__name__}: {err}"
                with self._socket_lock:
                    sock = self._socket
                    self._socket = None
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 2, 30.0)

    def diagnostics(self) -> dict[str, object]:
        return {
            "connected": self.stats.connected,
            "bytes_received": self.stats.bytes_received,
            "chunks_received": self.stats.chunks_received,
            "reconnects": self.stats.reconnects,
            "last_event_at": self.stats.last_event_at,
            "last_error": self.stats.last_error,
        }
