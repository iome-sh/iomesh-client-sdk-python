"""Kafka Produce subset client for I/O Mesh (TCP frame protocol).

Port of Go ``kafka.Client`` / ``iomeshclient.KafkaClient``.
Produce only — not a full Kafka consumer/admin client.
"""

from __future__ import annotations

import socket
import threading
from typing import Optional

from . import codec

API_PRODUCE = 0
ERR_NONE = 0
CLIENT_ID = "iomesh-kafka-client"
DEFAULT_ACKS = 1
DEFAULT_TIMEOUT_MS = 5000


class KafkaError(Exception):
    """Kafka protocol or produce failure."""


class KafkaClient:
    """Speaks the I/O Mesh Kafka protocol subset (Produce) for mesh integrations.

    Args:
        addr: Broker address ``host:port`` (e.g. ``127.0.0.1:9423``).
    """

    def __init__(self, addr: str) -> None:
        self.addr = (addr or "").strip()
        self._seq = 0
        self._lock = threading.Lock()
        self._conn: Optional[socket.socket] = None

    def produce(
        self,
        topic: str,
        partition: int,
        key: Optional[bytes],
        value: Optional[bytes],
        *,
        timeout_sec: float = 30.0,
    ) -> int:
        """Send one record to topic/partition; return broker base offset.

        Note: Go mesh Produce encodes the record with a nil key in the message
        set (key argument is accepted for API parity but not placed in the
        legacy message body — same as Go ``_ = key``).
        """
        if not self.addr:
            raise KafkaError("kafka: client addr not configured")
        topic = (topic or "").strip()
        if not topic:
            raise KafkaError("kafka: topic required")

        with self._lock:
            conn = self._conn_or_dial(timeout_sec)
            try:
                corr = self._next_corr()
                # Go: encodeMessageSetV1(value) — key ignored on wire
                record_set = codec.encode_message_set_v1(value, key=None)
                body = bytearray()
                body.extend(codec.write_int16(API_PRODUCE))
                body.extend(codec.write_int16(1))  # api version
                body.extend(codec.write_int32(corr))
                body.extend(codec.write_string(CLIENT_ID))
                body.extend(codec.write_int16(DEFAULT_ACKS))
                body.extend(codec.write_int32(DEFAULT_TIMEOUT_MS))
                body.extend(codec.write_int32(1))  # topic count
                body.extend(codec.write_string(topic))
                body.extend(codec.write_int32(1))  # partition count
                body.extend(codec.write_int32(int(partition)))
                body.extend(codec.write_bytes(record_set))

                frame = codec.write_frame(bytes(body))
                conn.sendall(frame)
                resp = self._read_frame(conn, timeout_sec)
                return self._parse_produce_response(resp, corr, topic, int(partition))
            except (OSError, KafkaError, ValueError) as e:
                self._close_unlocked()
                if isinstance(e, KafkaError):
                    raise
                raise KafkaError(f"kafka: produce failed: {e}") from e

    def close(self) -> None:
        """Close any persistent TCP connection."""
        with self._lock:
            self._close_unlocked()

    def __enter__(self) -> KafkaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- internals ---

    def _next_corr(self) -> int:
        self._seq += 1
        # keep in int32 range
        if self._seq > 0x7FFFFFFF:
            self._seq = 1
        return self._seq

    def _conn_or_dial(self, timeout_sec: float) -> socket.socket:
        if self._conn is not None:
            return self._conn
        host, _, port_s = self.addr.rpartition(":")
        if not host or not port_s:
            raise KafkaError(f"kafka: invalid addr {self.addr!r} (want host:port)")
        try:
            port = int(port_s)
        except ValueError as e:
            raise KafkaError(f"kafka: invalid port in addr {self.addr!r}") from e
        sock = socket.create_connection((host, port), timeout=timeout_sec)
        sock.settimeout(timeout_sec)
        self._conn = sock
        return sock

    def _close_unlocked(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None

    def _read_frame(self, conn: socket.socket, timeout_sec: float) -> bytes:
        conn.settimeout(timeout_sec)

        def recv_exact(n: int) -> bytes:
            buf = bytearray()
            while len(buf) < n:
                chunk = conn.recv(n - len(buf))
                if not chunk:
                    raise KafkaError("kafka: connection closed while reading frame")
                buf.extend(chunk)
            return bytes(buf)

        return codec.read_frame(recv_exact)

    def _parse_produce_response(
        self, resp: bytes, corr: int, topic: str, partition: int
    ) -> int:
        off = 0
        got_corr, off = codec.read_int32(resp, off)
        if got_corr != corr:
            raise KafkaError(f"kafka: correlation mismatch {got_corr} != {corr}")
        topic_count, off = codec.read_int32(resp, off)
        for _ in range(topic_count):
            got_topic, off = codec.read_string(resp, off)
            part_count, off = codec.read_int32(resp, off)
            if got_topic != topic:
                for _j in range(part_count):
                    _, off = codec.read_int32(resp, off)
                    _, off = codec.read_int16(resp, off)
                    _, off = codec.read_int64(resp, off)
                continue
            for _j in range(part_count):
                got_part, off = codec.read_int32(resp, off)
                code, off = codec.read_int16(resp, off)
                offset, off = codec.read_int64(resp, off)
                if got_part == partition:
                    if code != ERR_NONE:
                        raise KafkaError(f"kafka: produce error code {code}")
                    return offset
        raise KafkaError(
            f"kafka: topic {topic!r} partition {partition} missing from response"
        )
