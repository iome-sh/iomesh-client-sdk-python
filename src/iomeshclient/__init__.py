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
    "ConsumerInfo",
    "CreateBucketConfig",
    "CreateConsumerConfig",
    "DualWriteMemoryResult",
    "KVEntry",
    "KafkaClient",
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
    "connect",
    "format_catalog",
    "format_product_detail",
    "normalize_policy_mode",
]

__version__ = VERSION
