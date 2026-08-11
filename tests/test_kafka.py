"""Kafka Produce subset — codec unit tests + mock TCP Produce server."""

from __future__ import annotations

import socket
import struct
import threading

import pytest

from iomeshclient.kafka import KafkaClient, codec
from iomeshclient.kafka.client import KafkaError

# --- codec ---


def test_crc32c_stable() -> None:
    # empty
    assert codec.crc32c(b"") == 0
    # known Castagnoli vector (matches Go hash/crc32.Castagnoli)
    body = bytes([1, 0]) + struct.pack(">q", 0) + struct.pack(">i", -1)
    body += struct.pack(">i", 5) + b"hello"
    assert codec.crc32c(body) == 0xF3B282D1


def test_encode_decode_message_roundtrip() -> None:
    raw = codec.encode_message(b"k", b"v-payload")
    msg = codec.decode_message(raw)
    assert msg.magic == 1
    assert msg.attributes == 0
    assert msg.key == b"k"
    assert msg.value == b"v-payload"


def test_encode_message_nil_key() -> None:
    raw = codec.encode_message(None, b"hello")
    msg = codec.decode_message(raw)
    assert msg.key is None
    assert msg.value == b"hello"


def test_decode_message_crc_mismatch() -> None:
    raw = bytearray(codec.encode_message(None, b"x"))
    raw[0] ^= 0xFF
    with pytest.raises(ValueError, match="crc"):
        codec.decode_message(bytes(raw))


def test_message_set_v1_roundtrip() -> None:
    ms = codec.encode_message_set_v1(b"payload")
    values = codec.decode_message_set_v1(ms)
    assert values == [b"payload"]


def test_write_read_primitives() -> None:
    buf = (
        codec.write_int8(-3)
        + codec.write_int16(42)
        + codec.write_int32(1000)
        + codec.write_int64(9_000_000_000)
        + codec.write_string("topic-a")
        + codec.write_bytes(b"abc")
        + codec.write_bytes(None)
    )
    off = 0
    v, off = codec.read_int8(buf, off)
    assert v == -3
    v, off = codec.read_int16(buf, off)
    assert v == 42
    v, off = codec.read_int32(buf, off)
    assert v == 1000
    v, off = codec.read_int64(buf, off)
    assert v == 9_000_000_000
    s, off = codec.read_string(buf, off)
    assert s == "topic-a"
    b, off = codec.read_bytes(buf, off)
    assert b == b"abc"
    b, off = codec.read_bytes(buf, off)
    assert b is None
    assert off == len(buf)


def test_write_frame() -> None:
    frame = codec.write_frame(b"hi")
    assert frame[:4] == struct.pack(">i", 2)
    assert frame[4:] == b"hi"


# --- mock TCP Produce server ---


class _MockKafkaBroker:
    """Minimal Kafka Produce API v1 responder."""

    def __init__(self, *, offset: int = 42, error_code: int = 0) -> None:
        self.offset = offset
        self.error_code = error_code
        self.received: list[bytes] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def addr(self) -> str:
        return f"127.0.0.1:{self.port}"

    def close(self) -> None:
        self._stop.set()
        try:
            # wake accept
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                pass
        except OSError:
            pass
        self._sock.close()

    def _serve(self) -> None:
        self._sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            try:
                self._handle(conn)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(2.0)
        try:
            size_raw = _recv_exact(conn, 4)
        except (ConnectionError, TimeoutError, OSError):
            return
        (size,) = struct.unpack(">i", size_raw)
        if size <= 0:
            return
        try:
            body = _recv_exact(conn, size)
        except (ConnectionError, TimeoutError, OSError):
            return
        self.received.append(body)

        # parse request header
        off = 0
        api_key, off = codec.read_int16(body, off)
        _api_ver, off = codec.read_int16(body, off)
        corr, off = codec.read_int32(body, off)
        _client_id, off = codec.read_string(body, off)
        assert api_key == 0  # Produce

        # produce body: acks, timeout, topic_data
        _acks, off = codec.read_int16(body, off)
        _timeout, off = codec.read_int32(body, off)
        topic_count, off = codec.read_int32(body, off)
        topics: list[tuple[str, list[int]]] = []
        for _ in range(topic_count):
            topic, off = codec.read_string(body, off)
            part_count, off = codec.read_int32(body, off)
            parts: list[int] = []
            for _p in range(part_count):
                part, off = codec.read_int32(body, off)
                record_set, off = codec.read_bytes(body, off)
                parts.append(part)
                # ensure message set decodes
                if record_set:
                    codec.decode_message_set_v1(record_set)
            topics.append((topic, parts))

        # build produce response payload (after correlation)
        payload = bytearray()
        payload.extend(codec.write_int32(len(topics)))
        for topic, parts in topics:
            payload.extend(codec.write_string(topic))
            payload.extend(codec.write_int32(len(parts)))
            for part in parts:
                payload.extend(codec.write_int32(part))
                payload.extend(codec.write_int16(self.error_code))
                payload.extend(codec.write_int64(self.offset))

        resp_body = codec.write_int32(corr) + bytes(payload)
        conn.sendall(codec.write_frame(resp_body))


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf.extend(chunk)
    return bytes(buf)


@pytest.fixture
def kafka_broker():
    b = _MockKafkaBroker(offset=99)
    try:
        yield b
    finally:
        b.close()


def test_kafka_client_produce(kafka_broker) -> None:
    with KafkaClient(kafka_broker.addr) as kc:
        offset = kc.produce("events", 0, None, b'{"hello":"mesh"}')
    assert offset == 99
    assert len(kafka_broker.received) == 1
    # request header starts with api_key=0
    body = kafka_broker.received[0]
    api_key, _ = codec.read_int16(body, 0)
    assert api_key == 0
    # client_id present
    off = 2 + 2 + 4  # api_key, api_ver, corr
    client_id, _ = codec.read_string(body, off)
    assert client_id == "iomesh-kafka-client"


def test_kafka_client_produce_error_code() -> None:
    b = _MockKafkaBroker(offset=0, error_code=3)
    try:
        kc = KafkaClient(b.addr)
        with pytest.raises(KafkaError, match="error code 3"):
            kc.produce("missing", 0, None, b"x")
        kc.close()
    finally:
        b.close()


def test_kafka_client_addr_required() -> None:
    kc = KafkaClient("")
    with pytest.raises(KafkaError, match="addr not configured"):
        kc.produce("t", 0, None, b"x")


def test_kafka_client_topic_required(kafka_broker) -> None:
    kc = KafkaClient(kafka_broker.addr)
    with pytest.raises(KafkaError, match="topic required"):
        kc.produce("", 0, None, b"x")
    kc.close()


def test_import_from_package() -> None:
    from iomeshclient import KafkaClient as KC
    from iomeshclient.kafka import KafkaClient as KC2

    assert KC is KC2
