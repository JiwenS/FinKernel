from __future__ import annotations

from dataclasses import dataclass, field

from finkernel.connectors.brokers.base import BrokerAdapter


@dataclass
class BrokerRegistry:
    _brokers: dict[str, BrokerAdapter] = field(default_factory=dict)
    _default_slug: str | None = None

    def register(self, broker: BrokerAdapter, *, default: bool = False) -> None:
        self._brokers[broker.broker_slug] = broker
        if default or self._default_slug is None:
            self._default_slug = broker.broker_slug

    def get(self, slug: str | None = None) -> BrokerAdapter:
        resolved_slug = slug or self._default_slug
        if resolved_slug is None or resolved_slug not in self._brokers:
            raise KeyError(f"Unknown broker adapter: {resolved_slug}")
        return self._brokers[resolved_slug]

    def list_slugs(self) -> list[str]:
        return sorted(self._brokers)

    @property
    def default_slug(self) -> str | None:
        return self._default_slug
