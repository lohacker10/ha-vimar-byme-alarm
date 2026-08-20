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
from typing import Callable, Iterable


_CONTACT_FRAME = re.compile(
    rb"B4([0-9A-Fa-f]{4})0A02E20040([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})"
)


@dataclass(slots=True)
class VimarTcpStats:
    connected: bool = False
    bytes_received: int = 0
    chunks_received: int = 0
    reconnects: int = 0
    last_event_at: str | None = None
    last_error: str | None = None


ContactListener = Callable[[str, str, int], None]


class VimarTcpListener:
    """Receive-only listener on the Vimar event socket."""

    def __init__(
        self,
        host: str,
        port: int,
        on_data: Callable[[], None],
        *,
        contact_addresses: Iterable[str] = (),
    ) -> None:
        self.host = host
        self.port = port
        self.on_data = on_data
        self.stats = VimarTcpStats()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket_lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._tail = b""
        self._contact_addresses = {
            str(address).upper().zfill(4) for address in contact_addresses
        }
        self._contact_lock = threading.Lock()
        self._contact: dict[str, dict[str, object]] = {}
        self._changes: deque[dict[str, object]] = deque(maxlen=50)
        self._contact_listeners: set[ContactListener] = set()

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

    def add_contact_listener(self, listener: ContactListener) -> Callable[[], None]:
        with self._contact_lock:
            self._contact_listeners.add(listener)

        def _remove() -> None:
            with self._contact_lock:
                self._contact_listeners.discard(listener)

        return _remove

    def contact_state(self, address: str) -> dict[str, object] | None:
        key = str(address).upper().zfill(4)
        with self._contact_lock:
            value = self._contact.get(key)
            return dict(value) if value is not None else None

    def confirmed_contact_addresses(self) -> set[str]:
        with self._contact_lock:
            return {
                address
                for address, value in self._contact.items()
                if int(value.get("changes", 0)) > 0
            }

    def _parse(self, data: bytes) -> None:
        now = datetime.now(timezone.utc).isoformat()
        stream = self._tail + data
        notifications: list[tuple[str, str, int]] = []

        with self._contact_lock:
            for match in _CONTACT_FRAME.finditer(stream):
                address = match.group(1).decode("ascii").upper()
                if address not in self._contact_addresses:
                    continue

                byte_1 = match.group(2).decode("ascii").upper()
                byte_2 = match.group(3).decode("ascii").upper()
                previous_record = self._contact.get(address)
                previous_byte_1 = (
                    str(previous_record.get("byte_1", previous_record.get("state", "")))
                    if previous_record is not None
                    else None
                )
                previous_byte_2 = (
                    str(previous_record.get("byte_2", ""))
                    if previous_record is not None
                    else None
                )
                changes = (
                    int(previous_record.get("changes", 0))
                    if previous_record is not None
                    else 0
                )
                pair_changed = (
                    previous_record is not None
                    and (previous_byte_1 != byte_1 or previous_byte_2 != byte_2)
                )
                if pair_changed:
                    changes += 1

                self._contact[address] = {
                    "state": byte_1,
                    "byte_1": byte_1,
                    "byte_2": byte_2,
                    "changes": changes,
                    "last_seen": now,
                }

                if pair_changed:
                    self._changes.append(
                        {
                            "address": address,
                            "state": byte_1,
                            "byte_1": byte_1,
                            "byte_2": byte_2,
                            "previous_byte_1": previous_byte_1,
                            "previous_byte_2": previous_byte_2,
                            "changes": changes,
                            "at": now,
                        }
                    )
                    notifications.append((address, byte_1, changes))
            listeners = tuple(self._contact_listeners)

        self._tail = stream[-19:]
        for address, state, changes in notifications:
            for listener in listeners:
                listener(address, state, changes)

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
                        data = sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not data:
                        raise ConnectionError("Vimar TCP socket closed")
                    self.stats.bytes_received += len(data)
                    self.stats.chunks_received += 1
                    self.stats.last_event_at = datetime.now(timezone.utc).isoformat()
                    self._parse(data)
                    self.on_data()
            except Exception as err:
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
        with self._contact_lock:
            contact = {
                address: dict(value)
                for address, value in sorted(self._contact.items())
            }
            changes = list(self._changes)
        return {
            "connected": self.stats.connected,
            "bytes_received": self.stats.bytes_received,
            "chunks_received": self.stats.chunks_received,
            "reconnects": self.stats.reconnects,
            "last_event_at": self.stats.last_event_at,
            "last_error": self.stats.last_error,
            "contact_tcp_probe": {
                "raw_payload_retained": False,
                "diagnostic_fields": ["address", "byte_1", "byte_2", "timestamp"],
                "allowed_addresses": sorted(self._contact_addresses),
                "last_by_address": contact,
                "transitions": changes,
            },
        }
