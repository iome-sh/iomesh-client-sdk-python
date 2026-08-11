"""I/O Mesh HTTP client SDK for Python (official MIT edge client).

Parity target: github.com/iome-sh/iomesh-client-sdk-go (iomeshclient package).
Public lexicon: organizational heartbeats / ops pulse on dept.* streams.
Surfaces are Beta / pre-1.0 — not mesh control-plane GA.
"""

from .client import (
    VERSION,
    Client,
    ConnectOptions,
    ConsumerInfo,
    CreateConsumerConfig,
    Msg,
    PubAck,
    PullSubscribeConfig,
    StreamConfig,
    StreamInfo,
    Subscription,
    connect,
)
from .errors import APIError, ClientError

__all__ = [
    "VERSION",
    "APIError",
    "Client",
    "ClientError",
    "ConnectOptions",
    "ConsumerInfo",
    "CreateConsumerConfig",
    "Msg",
    "PubAck",
    "PullSubscribeConfig",
    "StreamConfig",
    "StreamInfo",
    "Subscription",
    "connect",
]

__version__ = VERSION
