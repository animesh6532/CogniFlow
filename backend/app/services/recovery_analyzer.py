"""Focus-recovery analysis for CogniFlow."""

from __future__ import annotations

from typing import Sequence

from app.models.event import Event


def _normalize_dt(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.min
    if getattr(dt, 'tzinfo', None) is not None:
        return dt.replace(tzinfo=None)
    return dt


class RecoveryAnalyzer:
    """Measure return to focused IDE activity after workflow changes."""

    FOCUSED_CONTEXT = "IDE"

    def analyze(
        self,
        events: Sequence[Event],
        interruptions: Sequence[dict],
        context_switches: Sequence[dict],
    ) -> list[int]:
        """
        Calculate recovery durations in seconds.

        Recovery is measured from an interruption or context switch
        until the developer returns to focused IDE activity.

        The next focused IDE event is used as the recovery point.
        """

        ordered_events = sorted(
            events,
            key=lambda event: (
                _normalize_dt(event.timestamp),
                event.id or 0,
            ),
        )

        if not ordered_events:
            return []

        recovery_values: list[int] = []

        # ----------------------------------------------------------
        # Build recovery trigger timestamps
        # ----------------------------------------------------------

        trigger_timestamps = self._build_trigger_timestamps(
            interruptions=interruptions,
            context_switches=context_switches,
        )

        if not trigger_timestamps:
            return recovery_values

        # ----------------------------------------------------------
        # Calculate recovery for every trigger
        # ----------------------------------------------------------

        for trigger_timestamp in trigger_timestamps:
            recovery_event = self._find_next_focused_event_after(
                events=ordered_events,
                timestamp=trigger_timestamp,
            )

            if recovery_event is None:
                continue

            evt_time = recovery_event.timestamp.replace(tzinfo=None) if recovery_event.timestamp and getattr(recovery_event.timestamp, 'tzinfo', None) else recovery_event.timestamp
            trig_time = trigger_timestamp.replace(tzinfo=None) if trigger_timestamp and getattr(trigger_timestamp, 'tzinfo', None) else trigger_timestamp

            seconds = int(
                max(
                    0,
                    (
                        evt_time
                        - trig_time
                    ).total_seconds(),
                )
            )

            recovery_values.append(seconds)

        return recovery_values

    def average_recovery_seconds(
        self,
        recovery_values: Sequence[int],
    ) -> float:
        """Return average recovery time in seconds."""

        if not recovery_values:
            return 0.0

        return sum(recovery_values) / len(recovery_values)

    def _build_trigger_timestamps(
        self,
        *,
        interruptions: Sequence[dict],
        context_switches: Sequence[dict],
    ) -> list:
        """
        Build the timestamps from which recovery should be measured.

        Interruption records use their own timestamp.

        Context-switch records use the timestamp of the switch itself.
        """

        timestamps = []

        # ----------------------------------------------------------
        # Interruption triggers
        # ----------------------------------------------------------

        for interruption in interruptions:
            timestamp = interruption.get("timestamp")

            if timestamp is not None:
                timestamps.append(timestamp)

        # ----------------------------------------------------------
        # Context-switch triggers
        # ----------------------------------------------------------

        for switch in context_switches:
            timestamp = switch.get("timestamp")

            if timestamp is not None:
                timestamps.append(timestamp)

        # ----------------------------------------------------------
        # Remove duplicate timestamps and sort
        # ----------------------------------------------------------

        normalized = [
            t.replace(tzinfo=None) if t and getattr(t, 'tzinfo', None) else t
            for t in timestamps
        ]

        return sorted(set(normalized))

    def _find_next_focused_event_after(
        self,
        *,
        events: Sequence[Event],
        timestamp,
    ) -> Event | None:
        """Return the first focused IDE event after a trigger."""

        trig_time = timestamp.replace(tzinfo=None) if timestamp and getattr(timestamp, 'tzinfo', None) else timestamp

        for event in events:
            evt_time = event.timestamp.replace(tzinfo=None) if event.timestamp and getattr(event.timestamp, 'tzinfo', None) else event.timestamp

            if evt_time <= trig_time:
                continue

            if self._is_focused(event):
                return event

        return None

    def _is_focused(
        self,
        event: Event,
    ) -> bool:
        """Return whether an event represents focused IDE activity."""

        source = (event.source or "").upper()
        context = (event.context or "").upper()

        return (
            source == self.FOCUSED_CONTEXT
            or context == self.FOCUSED_CONTEXT
        )