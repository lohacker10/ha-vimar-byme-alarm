"""Passive TCP listener for Vimar 01946 event notifications.

TCP is receive-only. Raw payloads are never exposed in diagnostics.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import socket
import threading
from typing import Callable


_CONTACT_FRAME = re.compile(rb"B4([0-9A-Fa-f]{4})0A02E20040([0-9A-Fa-f]{2})[0-9A-Fa-f]{2}")


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

    def __init__(self, host: str, port: int, on_data: Callable[[], None]) -> None:
        self.host = host
        self.port = port
        self.on_data = on_data
        self.stats = VimarTcpStats()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket_lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._tail = b""
        self._contact = {}
        self._changes = deque(maxlen=50)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="vimar-alarm-tcp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._socket_lock:
            sock = self._socket
            self._socket = None
        if sock:
            try:
                sock.close()
            except OSError:
                pass

    def _parse(self, data: bytes) -> None:
        now = datetime.now(timezone.utc).isoformat()
        stream = self._tail + data
        for match in _CONTACT_FRAME.finditer(stream):
            address = match.group(1).decode().upper()
            state = match.group(2).decode().upper()
            previous = self._contact.get(address, {}).get("state")
            self._contact[address] = {"state": state, "last_seen": now}
            if previous != state:
                self._changes.append({"address": address, "state": state, "at": now})
        self._tail = stream[-19:]

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sock = socket.create_connection((self.host, self.port), timeout=5)
                sock.settimeout(1)
                with self._socket_lock:
                    self._socket = sock
                self.stats.connected = True
                while not self._stop.is_set():
                    try:
                        data = sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not data:
                        raise ConnectionError("socket closed")
                    self.stats.bytes_received += len(data)
                    self.stats.chunks_received += 1
                    self.stats.last_event_at = datetime.now(timezone.utc).isoformat()
                    self._parse(data)
                    self.on_data()
            except Exception as err:
                self.stats.connected = False
                self.stats.last_error = f"{type(err).__name__}: {err}"
                if self._stop.wait(2):
                    return

    def diagnostics(self) -> dict[str, object]:
        return {
            "connected": self.stats.connected,
            "bytes_received": self.stats.bytes_received,
            "chunks_received": self.stats.chunks_received,
            "reconnects": self.stats.reconnects,
            "last_event_at": self.stats.last_event_at,
            "last_error": self.stats.last_error,
            "contact_tcp_probe": {
                "raw_payload_retained": False,
                "last_by_address": self._contact,
                "transitions": list(self._changes),
            },
        }
