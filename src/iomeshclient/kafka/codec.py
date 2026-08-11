"""Kafka wire primitives + legacy message (magic 1) encode/decode.

Port of Go ``kafka/codec.go`` essentials used by Produce.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

# CRC-32C (Castagnoli) — Kafka message CRC uses this poly (Go hash/crc32.Castagnoli).
# Prefer stdlib when present (zlib.crc32c on some 3.11+ builds); pure table otherwise.
_CRC32C_POLY = 0x82F63B78
_CRC32C_TABLE: list[int] = []


def _init_crc32c_table() -> None:
    table: list[int] = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ _CRC32C_POLY
            else:
                crc >>= 1
        table.append(crc & 0xFFFFFFFF)
    _CRC32C_TABLE.extend(table)


def _crc32c_pure(data: bytes) -> int:
    if not _CRC32C_TABLE:
        _init_crc32c_table()
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC32C_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


try:
    from zlib import crc32c as _zlib_crc32c  # type: ignore[attr-defined]

    def crc32c(data: bytes) -> int:
        """CRC-32C (Castagnoli) checksum of *data*."""
        return _zlib_crc32c(data) & 0xFFFFFFFF

except (ImportError, AttributeError):  # pragma: no cover

    def crc32c(data: bytes) -> int:
        """CRC-32C (Castagnoli) checksum of *data*."""
        return _crc32c_pure(data)


def write_int8(v: int) -> bytes:
    return struct.pack(">b", v)


def write_int16(v: int) -> bytes:
    return struct.pack(">h", v)


def write_int32(v: int) -> bytes:
    return struct.pack(">i", int(v))


def write_uint32(v: int) -> bytes:
    return struct.pack(">I", int(v) & 0xFFFFFFFF)


def write_int64(v: int) -> bytes:
    return struct.pack(">q", v)


def write_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    if len(raw) > 0x7FFF:
        raise ValueError("kafka: string too long")
    return write_int16(len(raw)) + raw


def write_bytes(b: Optional[bytes]) -> bytes:
    if b is None:
        return write_int32(-1)
    return write_int32(len(b)) + b


def write_frame(payload: bytes) -> bytes:
    if len(payload) > 0x7FFFFFFF:
        raise ValueError("kafka: frame too large")
    return write_int32(len(payload)) + payload


def read_int8(data: bytes, off: int) -> tuple[int, int]:
    if off + 1 > len(data):
        raise ValueError("kafka: unexpected EOF (int8)")
    (v,) = struct.unpack_from(">b", data, off)
    return v, off + 1


def read_int16(data: bytes, off: int) -> tuple[int, int]:
    if off + 2 > len(data):
        raise ValueError("kafka: unexpected EOF (int16)")
    (v,) = struct.unpack_from(">h", data, off)
    return v, off + 2


def read_int32(data: bytes, off: int) -> tuple[int, int]:
    if off + 4 > len(data):
        raise ValueError("kafka: unexpected EOF (int32)")
    (v,) = struct.unpack_from(">i", data, off)
    return v, off + 4


def read_int64(data: bytes, off: int) -> tuple[int, int]:
    if off + 8 > len(data):
        raise ValueError("kafka: unexpected EOF (int64)")
    (v,) = struct.unpack_from(">q", data, off)
    return v, off + 8


def read_string(data: bytes, off: int) -> tuple[str, int]:
    n, off = read_int16(data, off)
    if n < 0:
        return "", off
    if off + n > len(data):
        raise ValueError("kafka: unexpected EOF (string)")
    s = data[off : off + n].decode("utf-8")
    return s, off + n


def read_bytes(data: bytes, off: int) -> tuple[Optional[bytes], int]:
    n, off = read_int32(data, off)
    if n < 0:
        return None, off
    if off + n > len(data):
        raise ValueError("kafka: unexpected EOF (bytes)")
    return data[off : off + n], off + n


def read_frame(sock_recv_exact) -> bytes:
    """Read a 4-byte length-prefixed Kafka frame via *sock_recv_exact(n)*."""
    size_raw = sock_recv_exact(4)
    (size,) = struct.unpack(">i", size_raw)
    if size < 0:
        raise ValueError(f"kafka: invalid frame size {size}")
    if size == 0:
        return b""
    return sock_recv_exact(size)


@dataclass
class Message:
    """Legacy Kafka message (magic 0 or 1)."""

    magic: int = 1
    attributes: int = 0
    timestamp: int = 0
    key: Optional[bytes] = None
    value: Optional[bytes] = None


def encode_message(key: Optional[bytes], value: Optional[bytes]) -> bytes:
    """Build a legacy Kafka message (magic 1, no compression) with CRC-32C."""
    body = bytearray()
    body.append(1)  # magic
    body.append(0)  # attributes
    body.extend(write_int64(0))  # timestamp
    body.extend(write_bytes(key))
    body.extend(write_bytes(value))
    body_bytes = bytes(body)
    crc = crc32c(body_bytes)
    return write_uint32(crc) + body_bytes


def decode_message(data: bytes) -> Message:
    """Parse one message and verify CRC-32C."""
    if len(data) < 14:
        raise ValueError("kafka: message too short")
    stored_crc = struct.unpack_from(">I", data, 0)[0]
    magic = data[4]
    attributes = data[5]
    off = 6
    timestamp = 0
    if magic == 0:
        pass
    elif magic == 1:
        if len(data) < off + 8:
            raise ValueError("kafka: message v1 too short")
        timestamp = struct.unpack_from(">q", data, off)[0]
        off += 8
    else:
        raise ValueError(f"kafka: unsupported magic byte {magic}")

    key, n = _read_nullable_bytes_at(data, off)
    off += n
    value, n = _read_nullable_bytes_at(data, off)
    off += n
    if off != len(data):
        raise ValueError("kafka: trailing message bytes")

    if crc32c(data[4:]) != stored_crc:
        raise ValueError("kafka: crc mismatch")

    return Message(
        magic=magic,
        attributes=attributes,
        timestamp=timestamp,
        key=key,
        value=value,
    )


def encode_message_set_v1(value: Optional[bytes], key: Optional[bytes] = None) -> bytes:
    """Encode a single-record message set (offset 0 + size message).

    Go Produce uses key=nil for the record; *key* is accepted for symmetry.
    """
    raw = encode_message(key, value)
    return write_int64(0) + write_int32(len(raw)) + raw


def decode_message_set_v1(message_set: bytes) -> list[Optional[bytes]]:
    """Extract record values from a legacy message set (magic 0/1)."""
    values: list[Optional[bytes]] = []
    off = 0
    while off < len(message_set):
        _, off = read_int64(message_set, off)
        msg_size, off = read_int32(message_set, off)
        if msg_size < 0 or off + msg_size > len(message_set):
            raise ValueError("kafka: message set underflow")
        msg = decode_message(message_set[off : off + msg_size])
        off += msg_size
        values.append(msg.value)
    return values


def _read_nullable_bytes_at(data: bytes, off: int) -> tuple[Optional[bytes], int]:
    if off + 4 > len(data):
        raise ValueError("kafka: bytes length underflow")
    n = struct.unpack_from(">i", data, off)[0]
    if n < 0:
        return None, 4
    if off + 4 + n > len(data):
        raise ValueError("kafka: bytes payload underflow")
    if n == 0:
        return b"", 4
    return data[off + 4 : off + 4 + n], 4 + n
