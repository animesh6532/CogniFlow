"""Interruption detection for CogniFlow."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from app.models.event import Event


def _normalize_dt(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.min
    if getattr(dt, 'tzinfo', None) is not None:
        return dt.replace(tzinfo=None)
    return dt


class InterruptionAnalyzer:
    """Identify simulated activities that disrupt focused IDE work."""

    FOCUSED_CONTEXT = "IDE"

    # Activities that can meaningfully interrupt focused development.
    INTERRUPTION_SOURCES = {
        "SLACK",
        "JIRA",
        "GITHUB",
    }

    def analyze(self, events: Sequence[Event]) -> list[dict]:
        """Detect interruption events from a unified timeline."""

        ordered_events = sorted(
            events,
            key=lambda event: (_normalize_dt(event.timestamp), event.id or 0),
        )

        interruptions: list[dict] = []

        for index, event in enumerate(ordered_events):
            if not self._can_interrupt(event):
                continue

            previous = self._previous_event(
                ordered_events,
                index,
            )

            if previous is None:
                continue

            if not self._is_focused(previous):
                continue

            interruption_type = self._get_interruption_type(event)

            interruptions.append(
                {
                    "event_id": event.id,
                    "timestamp": event.timestamp,
                    "interruption_type": interruption_type,
                    "duration_seconds": self._estimate_duration(
                        ordered_events,
                        index,
                    ),
                    "description": (
                        f"{event.source} activity interrupted "
                        "focused IDE work."
                    ),
                }
            )

        return interruptions

    def _can_interrupt(self, event: Event) -> bool:
        source = (event.source or "").upper()
        context = (event.context or "").upper()

        return (
            source in self.INTERRUPTION_SOURCES
            or context in self.INTERRUPTION_SOURCES
        )

    def _is_focused(self, event: Event) -> bool:
        source = (event.source or "").upper()
        context = (event.context or "").upper()

        return (
            source == self.FOCUSED_CONTEXT
            or context == self.FOCUSED_CONTEXT
        )

    def _get_interruption_type(self, event: Event) -> str:
        source = (event.source or "").upper()

        if source == "SLACK":
            return "slack"

        if source == "JIRA":
            return "jira"

        if source == "GITHUB":
            return "github"

        return "workflow_activity"

    def _estimate_duration(
        self,
        events: Sequence[Event],
        index: int,
    ) -> int | None:
        """Estimate interruption duration from the next event.

        This is intentionally conservative. The event model contains
        timestamps rather than an explicit duration for source events.
        """

        if index + 1 >= len(events):
            return None

        current = events[index]
        next_event = events[index + 1]

        c_time = current.timestamp.replace(tzinfo=None) if current.timestamp and getattr(current.timestamp, 'tzinfo', None) else current.timestamp
        n_time = next_event.timestamp.replace(tzinfo=None) if next_event.timestamp and getattr(next_event.timestamp, 'tzinfo', None) else next_event.timestamp

        seconds = int(
            max(
                0,
                (n_time - c_time).total_seconds(),
            )
        )

        return seconds if seconds > 0 else None

    @staticmethod
    def _previous_event(
        events: Sequence[Event],
        index: int,
    ) -> Event | None:
        if index == 0:
            return None

        return events[index - 1]