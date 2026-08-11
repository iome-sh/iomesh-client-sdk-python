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
    ListStreamMessagesOptions,
    Msg,
    PubAck,
    PullSubscribeConfig,
    StreamConfig,
    StreamInfo,
    StreamMessage,
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
from .kv_format import (
    format_bucket_info,
    format_kv_entry,
    format_kv_keys,
    format_put_result,
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
from .metering import (
    STREAM_DEPT,
    TYPE_DEPT_AGENT_LLM_CALL,
    DeptEvent,
    LLMCallEvent,
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
    format_consumer_info,
    format_msg,
    format_msgs,
    format_stream_detail,
    format_streams,
)

__all__ = [
    "POLICY_ADVISORY",
    "POLICY_ENFORCE",
    "POLICY_OFF",
    "STREAM_DEPT",
    "TYPE_DEPT_AGENT_LLM_CALL",
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
    "DeptEvent",
    "DualWriteMemoryResult",
    "KVEntry",
    "KafkaClient",
    "LLMCallEvent",
    "LineageRef",
    "ListStreamMessagesOptions",
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
    "StreamMessage",
    "Subscription",
    "WaitReadyResult",
    "aggregate_connection_result",
    "connect",
    "format_bucket_info",
    "format_catalog",
    "format_connection_status",
    "format_consumer_info",
    "format_context_snippet",
    "format_kv_entry",
    "format_kv_keys",
    "format_msg",
    "format_msgs",
    "format_product_detail",
    "format_put_result",
    "format_stream_detail",
    "format_streams",
    "normalize_policy_mode",
]

__version__ = VERSION
