from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class CounterSnapshot:
    state_transitions: dict[str, int]
    broker_outcomes: dict[str, int]
    reconciliation_outcomes: dict[str, int]


class ObservabilityService:
    def __init__(self) -> None:
        self._state_transitions: Counter[str] = Counter()
        self._broker_outcomes: Counter[str] = Counter()
        self._reconciliation_outcomes: Counter[str] = Counter()
        self._lock = Lock()

    def record_state_transition(self, *, previous_state: str, new_state: str) -> None:
        key = f"{previous_state}->{new_state}"
        with self._lock:
            self._state_transitions[key] += 1

    def record_broker_outcome(self, *, outcome: str) -> None:
        with self._lock:
            self._broker_outcomes[outcome] += 1

    def record_reconciliation_outcome(self, *, outcome: str) -> None:
        with self._lock:
            self._reconciliation_outcomes[outcome] += 1

    def snapshot(self) -> CounterSnapshot:
        with self._lock:
            return CounterSnapshot(
                state_transitions=dict(self._state_transitions),
                broker_outcomes=dict(self._broker_outcomes),
                reconciliation_outcomes=dict(self._reconciliation_outcomes),
            )
