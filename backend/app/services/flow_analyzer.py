"""Flow-session analysis for CogniFlow."""

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


class FlowAnalyzer:
    """Detect sustained IDE-focused development sessions."""

    # The PDF does not specify this threshold.
    # This is an implementation decision and can be changed later.
    DEFAULT_MAX_FOCUS_GAP_SECONDS = 30 * 60

    FOCUSED_SOURCE = "IDE"
    FOCUSED_CONTEXTS = {"IDE"}

    def __init__(
        self,
        *,
        max_focus_gap_seconds: int = DEFAULT_MAX_FOCUS_GAP_SECONDS,
    ) -> None:
        if max_focus_gap_seconds <= 0:
            raise ValueError("Focus gap must be greater than zero.")

        self.max_focus_gap_seconds = max_focus_gap_seconds

    def is_focused_event(self, event: Event) -> bool:
        """Return True when an event represents focused development."""

        source = (event.source or "").upper()
        context = (event.context or "").upper()

        return (
            source == self.FOCUSED_SOURCE
            or context in self.FOCUSED_CONTEXTS
        )

    def analyze(self, events: Sequence[Event]) -> list[dict]:
        """Convert chronological IDE activity into flow sessions."""

        ordered_events = sorted(
            events,
            key=lambda event: (_normalize_dt(event.timestamp), event.id or 0),
        )

        sessions: list[dict] = []
        current_events: list[Event] = []

        for event in ordered_events:
            if not self.is_focused_event(event):
                self._close_current_session(current_events, sessions)
                current_events = []
                continue

            if not current_events:
                current_events = [event]
                continue

            previous = current_events[-1]

            gap = self._seconds_between(
                previous.timestamp,
                event.timestamp,
            )

            if gap <= self.max_focus_gap_seconds:
                current_events.append(event)
            else:
                self._close_current_session(
                    current_events,
                    sessions,
                )
                current_events = [event]

        self._close_current_session(current_events, sessions)

        return sessions

    def _close_current_session(
        self,
        events: list[Event],
        sessions: list[dict],
    ) -> None:
        if not events:
            return

        start_time = events[0].timestamp
        end_time = events[-1].timestamp

        s_time = start_time.replace(tzinfo=None) if start_time and getattr(start_time, 'tzinfo', None) else start_time
        e_time = end_time.replace(tzinfo=None) if end_time and getattr(end_time, 'tzinfo', None) else end_time

        duration_seconds = max(
            0,
            int((e_time - s_time).total_seconds()),
        )

        sessions.append(
            {
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration_seconds,
                "focused_event_count": len(events),
                "notes": (
                    "Detected from sustained simulated IDE "
                    "development activity."
                ),
            }
        )

    @staticmethod
    def _seconds_between(
        start: datetime,
        end: datetime,
    ) -> float:
        s = start.replace(tzinfo=None) if start and getattr(start, 'tzinfo', None) else start
        e = end.replace(tzinfo=None) if end and getattr(end, 'tzinfo', None) else end
        return max(0.0, (e - s).total_seconds())