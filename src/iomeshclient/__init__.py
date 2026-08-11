"""I/O Mesh HTTP client SDK for Python (official MIT edge client).

Parity target: github.com/iome-sh/iomesh-client-sdk-go (iomeshclient package).
Public lexicon: organizational heartbeats / ops pulse on dept.* streams.
Surfaces are Beta / pre-1.0 — not mesh control-plane GA.
"""

from .catalog import (
    CatalogProduct,
    CatalogResult,
    format_catalog,
    format_product_detail,
)
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
    WaitReadyResult,
    connect,
)
from .context import (
    ContextResult,
    LineageRef,
    format_context_snippet,
)
from .errors import APIError, ClientError
from .kafka import KafkaClient
from .kv import (
    BucketInfo,
    CreateBucketConfig,
    KVEntry,
    PutResult,
)
from .memory import (
    DualWriteMemoryResult,
    MemoryEntityRef,
    MemoryEnvelope,
    MemoryHit,
    MemoryIngestResponse,
    MemoryOpsDigestDecisionStub,
    MemoryOpsDigestHonesty,
    MemoryOpsDigestPattern,
    MemoryOpsDigestReceipt,
    MemoryOpsDigestResponse,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
)
from .policy import (
    POLICY_ADVISORY,
    POLICY_ENFORCE,
    POLICY_OFF,
    PolicyDecision,
    PolicyInput,
    normalize_policy_mode,
)
from .status import (
    ConnectionStatus,
    aggregate_connection_result,
    format_connection_status,
)
from .streams_format import (
    format_stream_detail,
    format_streams,
)

__all__ = [
    "POLICY_ADVISORY",
    "POLICY_ENFORCE",
    "POLICY_OFF",
    "VERSION",
    "APIError",
    "BucketInfo",
    "CatalogProduct",
    "CatalogResult",
    "Client",
    "ClientError",
    "ConnectOptions",
    "ConnectionStatus",
    "ConsumerInfo",
    "ContextResult",
    "CreateBucketConfig",
    "CreateConsumerConfig",
    "DualWriteMemoryResult",
    "KVEntry",
    "KafkaClient",
    "LineageRef",
    "MemoryEntityRef",
    "MemoryEnvelope",
    "MemoryHit",
    "MemoryIngestResponse",
    "MemoryOpsDigestDecisionStub",
    "MemoryOpsDigestHonesty",
    "MemoryOpsDigestPattern",
    "MemoryOpsDigestReceipt",
    "MemoryOpsDigestResponse",
    "MemoryRetrieveRequest",
    "MemoryRetrieveResponse",
    "Msg",
    "PolicyDecision",
    "PolicyInput",
    "PubAck",
    "PullSubscribeConfig",
    "PutResult",
    "StreamConfig",
    "StreamInfo",
    "Subscription",
    "WaitReadyResult",
    "aggregate_connection_result",
    "connect",
    "format_catalog",
    "format_connection_status",
    "format_context_snippet",
    "format_product_detail",
    "format_stream_detail",
    "format_streams",
    "normalize_policy_mode",
]

__version__ = VERSION
