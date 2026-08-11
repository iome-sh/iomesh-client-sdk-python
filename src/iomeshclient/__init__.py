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
    connect_from_env,
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
from .liveview import (
    PROCESSOR_TYPE_ENRICH,
    PROCESSOR_TYPE_FILTER,
    PROCESSOR_TYPE_MAP,
    DataProduct,
    LiveView,
    ProcessorConfig,
)
from .memory import (
    STREAM_MEMORY_INGEST,
    STREAM_MEMORY_RPC,
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
    MemoryRecallRequest,
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
    "PROCESSOR_TYPE_ENRICH",
    "PROCESSOR_TYPE_FILTER",
    "PROCESSOR_TYPE_MAP",
    "STREAM_DEPT",
    "STREAM_MEMORY_INGEST",
    "STREAM_MEMORY_RPC",
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
    "DataProduct",
    "DeptEvent",
    "DualWriteMemoryResult",
    "KVEntry",
    "KafkaClient",
    "LLMCallEvent",
    "LineageRef",
    "ListStreamMessagesOptions",
    "LiveView",
    "MemoryEntityRef",
    "MemoryEnvelope",
    "MemoryHit",
    "MemoryIngestResponse",
    "MemoryOpsDigestDecisionStub",
    "MemoryOpsDigestHonesty",
    "MemoryOpsDigestPattern",
    "MemoryOpsDigestReceipt",
    "MemoryOpsDigestResponse",
    "MemoryRecallRequest",
    "MemoryRetrieveRequest",
    "MemoryRetrieveResponse",
    "Msg",
    "PolicyDecision",
    "PolicyInput",
    "ProcessorConfig",
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
    "connect_from_env",
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
