"""Kafka Produce subset for I/O Mesh integrations and pilots.

Honesty:
- **Produce only** — not a full Kafka client (no consumer group, fetch, metadata, etc.)
- Mesh protocol subset for integrations / pilots · not freemium palace
- Wire parity with Go ``github.com/iome-sh/iomesh-client-sdk-go/kafka``
"""

from .client import KafkaClient

__all__ = ["KafkaClient"]
